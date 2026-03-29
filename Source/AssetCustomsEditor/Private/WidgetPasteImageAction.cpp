#include "WidgetPasteImageAction.h"
#include "ClipboardImageUtils.h"

#include "WidgetBlueprint.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Image.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Engine/Texture2D.h"
#include "ImageUtils.h"
#include "ImageCore.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Misc/Guid.h"
#include "Misc/PackageName.h"
#include "Misc/SecureHash.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "Framework/Notifications/NotificationManager.h"
#include "Widgets/Notifications/SNotificationList.h"
#include "EditorAssetLibrary.h"

DEFINE_LOG_CATEGORY_STATIC(LogAssetCustoms, Log, All);

/**
 * Ensure all widgets in the WidgetTree have entries in WidgetVariableNameToGuidMap.
 * Without this, the Widget Blueprint compiler asserts on missing GUIDs.
 */
static void EnsureWidgetVariableGuids(UWidgetBlueprint* WidgetBlueprint)
{
    if (!WidgetBlueprint || !WidgetBlueprint->WidgetTree)
    {
        return;
    }

    WidgetBlueprint->WidgetTree->ForEachWidget([&](UWidget* Widget)
    {
        if (!Widget)
        {
            return;
        }
        const FName WidgetFName = Widget->GetFName();
        if (!WidgetBlueprint->WidgetVariableNameToGuidMap.Contains(WidgetFName))
        {
            WidgetBlueprint->WidgetVariableNameToGuidMap.Add(WidgetFName, FGuid::NewGuid());
        }
    });
}

/**
 * Compute a short MD5 hash (first 8 hex chars) from pixel data for deduplication.
 */
static FString ComputePixelHash(const TArray<uint8>& PixelData)
{
    FMD5 Md5;
    Md5.Update(PixelData.GetData(), PixelData.Num());

    uint8 Digest[16];
    Md5.Final(Digest);

    // Use first 8 hex chars for a short but sufficient identifier
    return FString::Printf(TEXT("%02x%02x%02x%02x"), Digest[0], Digest[1], Digest[2], Digest[3]);
}

/**
 * Try to find an existing texture asset with the given hash-based name.
 * Returns the existing UTexture2D if found, nullptr otherwise.
 */
static UTexture2D* FindExistingTextureByHash(const FString& TargetDir, const FString& AssetName)
{
    const FString FullPath = TargetDir / AssetName;
    UObject* Existing = UEditorAssetLibrary::LoadAsset(FullPath);
    return Cast<UTexture2D>(Existing);
}

/**
 * Create a persistent Texture2D asset from BGRA8 pixel data, or reuse existing.
 * Asset name is derived from pixel content hash to avoid duplicates.
 */
static UTexture2D* CreateOrReuseTextureFromPixels(const FClipboardImageData& ImageData, const FString& TargetDir)
{
    // Hash-based deduplication: same pixels → same asset name
    const FString PixelHash = ComputePixelHash(ImageData.PixelData);
    const FString AssetName = FString::Printf(TEXT("T_Pasted_%s"), *PixelHash);

    // Check if texture with this hash already exists
    UTexture2D* Existing = FindExistingTextureByHash(TargetDir, AssetName);
    if (Existing)
    {
        UE_LOG(LogAssetCustoms, Log, TEXT("Reusing existing texture: %s"), *Existing->GetPathName());
        return Existing;
    }

    // Build asset path in the same directory as the Widget Blueprint
    const FString PackagePath = TargetDir / AssetName;

    UPackage* Package = CreatePackage(*PackagePath);
    if (!Package)
    {
        UE_LOG(LogAssetCustoms, Error, TEXT("Failed to create package: %s"), *PackagePath);
        return nullptr;
    }
    Package->FullyLoad();

    // Build FImage from raw BGRA8 pixels
    FImage SourceImage(ImageData.Width, ImageData.Height, ERawImageFormat::BGRA8, EGammaSpace::sRGB);
    if (SourceImage.RawData.Num() != ImageData.PixelData.Num())
    {
        UE_LOG(LogAssetCustoms, Error, TEXT("Pixel data size mismatch: expected %d, got %d"), SourceImage.RawData.Num(), ImageData.PixelData.Num());
        return nullptr;
    }
    FMemory::Memcpy(SourceImage.RawData.GetData(), ImageData.PixelData.GetData(), ImageData.PixelData.Num());

    // Create persistent editor texture (fills TextureSource, builds platform data)
    UTexture* TextureBase = FImageUtils::CreateTexture(
        ETextureClass::TwoD,
        SourceImage,
        Package,
        AssetName,
        RF_Public | RF_Standalone,
        true // DoPostEditChange
    );

    UTexture2D* Texture = Cast<UTexture2D>(TextureBase);
    if (!Texture)
    {
        UE_LOG(LogAssetCustoms, Error, TEXT("FImageUtils::CreateTexture failed for %s"), *AssetName);
        return nullptr;
    }

    // Set UI-friendly defaults
    Texture->LODGroup = TEXTUREGROUP_UI;
    Texture->CompressionSettings = TC_EditorIcon;
    Texture->MipGenSettings = TMGS_NoMipmaps;
    Texture->NeverStream = true;
    Texture->PostEditChange();

    // Register with asset registry so Content Browser sees it
    FAssetRegistryModule::AssetCreated(Texture);

    // Save to disk as .uasset
    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
    FString PackageFilename = FPackageName::LongPackageNameToFilename(PackagePath, FPackageName::GetAssetPackageExtension());
    bool bSaved = UPackage::SavePackage(Package, Texture, *PackageFilename, SaveArgs);
    if (!bSaved)
    {
        UE_LOG(LogAssetCustoms, Warning, TEXT("Failed to save texture package to disk: %s"), *PackageFilename);
    }

    UE_LOG(LogAssetCustoms, Log, TEXT("Created texture: %s (%dx%d)"), *PackagePath, ImageData.Width, ImageData.Height);
    return Texture;
}

/** Show an editor notification toast. */
static void ShowNotification(const FText& Message, SNotificationItem::ECompletionState State = SNotificationItem::CS_Fail)
{
    FNotificationInfo Info(Message);
    Info.ExpireDuration = 3.0f;
    Info.bUseLargeFont = false;
    TSharedPtr<SNotificationItem> Notification = FSlateNotificationManager::Get().AddNotification(Info);
    if (Notification.IsValid())
    {
        Notification->SetCompletionState(State);
    }
}

void WidgetPasteImageAction::Execute(UWidgetBlueprint* WidgetBlueprint)
{
    if (!WidgetBlueprint)
    {
        UE_LOG(LogAssetCustoms, Warning, TEXT("PasteImage: No Widget Blueprint provided"));
        return;
    }

    // Step 1: Check clipboard for image — show notification if none
    if (!ClipboardImageUtils::HasClipboardImage())
    {
        ShowNotification(
            NSLOCTEXT("AssetCustoms", "NoImageInClipboard", "Clipboard does not contain an image.\nCopy an image first, then try again."));
        UE_LOG(LogAssetCustoms, Warning, TEXT("PasteImage: No image in clipboard"));
        return;
    }

    FClipboardImageData ClipboardData;
    if (!ClipboardImageUtils::GrabClipboardImage(ClipboardData))
    {
        ShowNotification(
            NSLOCTEXT("AssetCustoms", "ClipboardReadFailed", "Failed to read image from clipboard.\nThe clipboard format may not be supported (only bitmap/PNG)."));
        UE_LOG(LogAssetCustoms, Error, TEXT("PasteImage: Failed to read clipboard image"));
        return;
    }

    // Step 2: Derive target directory from the Widget Blueprint's package path
    const FString WBPPackageName = WidgetBlueprint->GetOutermost()->GetName();
    const FString TargetDir = FPackageName::GetLongPackagePath(WBPPackageName);

    // Step 3: Create or reuse Texture2D asset (hash-based dedup, same directory as WBP)
    UTexture2D* Texture = CreateOrReuseTextureFromPixels(ClipboardData, TargetDir);
    if (!Texture)
    {
        return;
    }

    // Step 4: Create Image widget in the WidgetTree
    UWidgetTree* WidgetTree = WidgetBlueprint->WidgetTree;
    if (!WidgetTree)
    {
        UE_LOG(LogAssetCustoms, Error, TEXT("PasteImage: WidgetTree is null"));
        return;
    }

    UCanvasPanel* RootCanvas = Cast<UCanvasPanel>(WidgetTree->RootWidget);
    if (!RootCanvas)
    {
        UE_LOG(LogAssetCustoms, Error, TEXT("PasteImage: Root widget is not a Canvas Panel"));
        return;
    }

    const FString ImageName = FString::Printf(TEXT("IMG_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Short).Left(8));
    UImage* ImageWidget = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass(), *ImageName);
    if (!ImageWidget)
    {
        UE_LOG(LogAssetCustoms, Error, TEXT("PasteImage: Failed to construct Image widget"));
        return;
    }

    // Bind texture and match original image size
    ImageWidget->SetBrushFromTexture(Texture, /*bMatchSize=*/ true);

    // Add to canvas
    UCanvasPanelSlot* Slot = RootCanvas->AddChildToCanvas(ImageWidget);
    if (Slot)
    {
        Slot->SetAutoSize(true);
    }

    // Step 5: Mark dirty and trigger immediate recompilation so Designer refreshes
    EnsureWidgetVariableGuids(WidgetBlueprint);
    WidgetBlueprint->MarkPackageDirty();

    if (!WidgetBlueprint->bBeingCompiled && WidgetBlueprint->Status != BS_BeingCreated)
    {
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBlueprint);
    }

    UE_LOG(LogAssetCustoms, Log, TEXT("PasteImage: Added Image '%s' with texture '%s' to '%s'"),
        *ImageName, *Texture->GetPathName(), *WidgetBlueprint->GetName());
}
