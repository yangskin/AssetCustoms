#include "WidgetReplaceTextureFromClipboardAction.h"

#include "ClipboardImageUtils.h"
#include "WidgetClipboardTextureUtils.h"

#include "Blueprint/WidgetTree.h"
#include "Components/Image.h"
#include "EditorFramework/AssetImportData.h"
#include "EditorReimportHandler.h"
#include "Engine/Texture2D.h"
#include "Framework/Notifications/NotificationManager.h"
#include "HAL/FileManager.h"
#include "ImageCore.h"
#include "ImageUtils.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "WidgetBlueprint.h"
#include "WidgetBlueprintEditor.h"
#include "WidgetReference.h"
#include "Widgets/Notifications/SNotificationList.h"

DEFINE_LOG_CATEGORY_STATIC(LogAssetCustomsClipboardReimport, Log, All);

namespace
{
    void ShowNotification(const FText& Message, SNotificationItem::ECompletionState State)
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

    bool TryGetSelectedImage(FWidgetBlueprintEditor* BlueprintEditor, UImage*& OutImage, UTexture2D*& OutTexture)
    {
        OutImage = nullptr;
        OutTexture = nullptr;

        if (!BlueprintEditor)
        {
            return false;
        }

        const TSet<FWidgetReference>& SelectedWidgets = BlueprintEditor->GetSelectedWidgets();
        if (SelectedWidgets.Num() != 1)
        {
            return false;
        }

        const FWidgetReference& WidgetRef = *SelectedWidgets.CreateConstIterator();
        OutImage = Cast<UImage>(WidgetRef.GetTemplate());
        if (!OutImage)
        {
            return false;
        }

        OutTexture = Cast<UTexture2D>(OutImage->GetBrush().GetResourceObject());
        return true;
    }

    FString BuildClipboardSourceFilename(const UTexture2D* Texture)
    {
        const FString TextureName = Texture ? Texture->GetName() : TEXT("ClipboardTexture");
        const FString TexturePath = Texture ? Texture->GetPathName() : TextureName;
        const FString TextureHash = FMD5::HashAnsiString(*TexturePath).Left(8);
        const FString SafeName = FPaths::MakeValidFileName(TextureName);
        return FString::Printf(TEXT("%s_%s.png"), *SafeName, *TextureHash);
    }

    FString BuildClipboardSourcePath(const UTexture2D* Texture)
    {
        return FPaths::Combine(
            FPaths::ProjectSavedDir(),
            TEXT("AssetCustoms"),
            TEXT("ClipboardTextureSources"),
            BuildClipboardSourceFilename(Texture));
    }

    bool SaveClipboardImageToDisk(const FClipboardImageData& ImageData, const FString& OutputFilename)
    {
        const FString OutputDirectory = FPaths::GetPath(OutputFilename);
        if (!IFileManager::Get().MakeDirectory(*OutputDirectory, true))
        {
            UE_LOG(LogAssetCustomsClipboardReimport, Error, TEXT("Failed to create clipboard source directory: %s"), *OutputDirectory);
            return false;
        }

        FImage ClipboardImage(ImageData.Width, ImageData.Height, ERawImageFormat::BGRA8, EGammaSpace::sRGB);
        if (ClipboardImage.RawData.Num() != ImageData.PixelData.Num())
        {
            UE_LOG(LogAssetCustomsClipboardReimport, Error, TEXT("Clipboard image size mismatch. Expected %d bytes, got %d bytes."), ClipboardImage.RawData.Num(), ImageData.PixelData.Num());
            return false;
        }

        FMemory::Memcpy(ClipboardImage.RawData.GetData(), ImageData.PixelData.GetData(), ImageData.PixelData.Num());
        return FImageUtils::SaveImageByExtension(*OutputFilename, ClipboardImage);
    }

    UAssetImportData* EnsureAssetImportData(UTexture2D* Texture)
    {
        if (!Texture)
        {
            return nullptr;
        }

        if (!Texture->AssetImportData)
        {
            Texture->AssetImportData = NewObject<UAssetImportData>(Texture, TEXT("AssetImportData"));
        }

        return Texture->AssetImportData;
    }
}

namespace WidgetReplaceTextureFromClipboardAction
{
    bool CanExecute(const FWidgetBlueprintEditor* BlueprintEditor)
    {
        if (!BlueprintEditor || !ClipboardImageUtils::HasClipboardImage())
        {
            return false;
        }

        UImage* ImageWidget = nullptr;
        UTexture2D* Texture = nullptr;
        return TryGetSelectedImage(const_cast<FWidgetBlueprintEditor*>(BlueprintEditor), ImageWidget, Texture);
    }

    void Execute(FWidgetBlueprintEditor* BlueprintEditor)
    {
        UImage* ImageWidget = nullptr;
        UTexture2D* Texture = nullptr;
        if (!TryGetSelectedImage(BlueprintEditor, ImageWidget, Texture))
        {
            ShowNotification(
                NSLOCTEXT("AssetCustoms", "ClipboardReimportInvalidSelection", "Select a single Image widget."),
                SNotificationItem::CS_Fail);
            return;
        }

        UWidgetBlueprint* WidgetBlueprint = BlueprintEditor ? BlueprintEditor->GetWidgetBlueprintObj() : nullptr;
        if (!WidgetBlueprint)
        {
            ShowNotification(
                NSLOCTEXT("AssetCustoms", "ClipboardReimportNoBlueprint", "Failed to resolve the active Widget Blueprint."),
                SNotificationItem::CS_Fail);
            return;
        }

        if (!ClipboardImageUtils::HasClipboardImage())
        {
            ShowNotification(
                NSLOCTEXT("AssetCustoms", "ClipboardReimportNoImage", "Clipboard does not contain an image."),
                SNotificationItem::CS_Fail);
            return;
        }

        FClipboardImageData ClipboardData;
        if (!ClipboardImageUtils::GrabClipboardImage(ClipboardData))
        {
            ShowNotification(
                NSLOCTEXT("AssetCustoms", "ClipboardReimportReadFailed", "Failed to read clipboard image data."),
                SNotificationItem::CS_Fail);
            return;
        }

        if (!Texture)
        {
            const FString WidgetPackageName = WidgetBlueprint->GetOutermost()->GetName();
            const FString TargetDir = FPackageName::GetLongPackagePath(WidgetPackageName);
            UTexture2D* ImportedTexture = WidgetClipboardTextureUtils::CreateOrReuseTextureFromPixels(ClipboardData, TargetDir);
            if (!ImportedTexture)
            {
                ShowNotification(
                    NSLOCTEXT("AssetCustoms", "ClipboardBrushImportFailed", "Failed to create or reuse a texture asset from clipboard image data."),
                    SNotificationItem::CS_Fail);
                return;
            }

            WidgetBlueprint->Modify();
            if (WidgetBlueprint->WidgetTree)
            {
                WidgetBlueprint->WidgetTree->Modify();
            }
            ImageWidget->Modify();
            ImageWidget->SetBrushFromTexture(ImportedTexture, false);

            WidgetBlueprint->MarkPackageDirty();
            FBlueprintEditorUtils::MarkBlueprintAsModified(WidgetBlueprint);
            BlueprintEditor->InvalidatePreview(false);

            ShowNotification(
                FText::Format(
                    NSLOCTEXT("AssetCustoms", "ClipboardBrushImportSucceeded", "Assigned clipboard texture '{0}' to the selected Image brush."),
                    FText::FromString(ImportedTexture->GetName())),
                SNotificationItem::CS_Success);
            return;
        }

        const FString SourceFilename = BuildClipboardSourcePath(Texture);
        if (!SaveClipboardImageToDisk(ClipboardData, SourceFilename))
        {
            ShowNotification(
                NSLOCTEXT("AssetCustoms", "ClipboardReimportSaveFailed", "Failed to write managed clipboard PNG source file."),
                SNotificationItem::CS_Fail);
            return;
        }

        UAssetImportData* AssetImportData = EnsureAssetImportData(Texture);
        if (!AssetImportData)
        {
            ShowNotification(
                NSLOCTEXT("AssetCustoms", "ClipboardReimportImportDataFailed", "Failed to prepare texture import data."),
                SNotificationItem::CS_Fail);
            return;
        }

        Texture->Modify();
        AssetImportData->Modify();
        AssetImportData->UpdateFilenameOnly(SourceFilename);

        const bool bReimported = FReimportManager::Instance()->Reimport(
            Texture,
            false,
            false,
            TEXT(""),
            nullptr,
            INDEX_NONE,
            false,
            true,
            false);

        if (!bReimported)
        {
            UE_LOG(LogAssetCustomsClipboardReimport, Warning, TEXT("Clipboard reimport failed for texture: %s"), *Texture->GetPathName());
            ShowNotification(
                FText::Format(
                    NSLOCTEXT("AssetCustoms", "ClipboardReimportFailed", "Reimport failed for texture '{0}'."),
                    FText::FromString(Texture->GetName())),
                SNotificationItem::CS_Fail);
            return;
        }

        ShowNotification(
            FText::Format(
                NSLOCTEXT("AssetCustoms", "ClipboardReimportSucceeded", "Reimported texture '{0}' from clipboard image."),
                FText::FromString(Texture->GetName())),
            SNotificationItem::CS_Success);
    }
}