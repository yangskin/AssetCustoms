#include "WidgetClipboardTextureUtils.h"

#include "ClipboardImageUtils.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "EditorAssetLibrary.h"
#include "Engine/Texture2D.h"
#include "ImageCore.h"
#include "ImageUtils.h"
#include "Misc/PackageName.h"
#include "Misc/SecureHash.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

DEFINE_LOG_CATEGORY_STATIC(LogAssetCustomsClipboardImport, Log, All);

namespace
{
    FString ComputePixelHash(const TArray<uint8>& PixelData)
    {
        FMD5 Md5;
        Md5.Update(PixelData.GetData(), PixelData.Num());

        uint8 Digest[16];
        Md5.Final(Digest);

        return FString::Printf(TEXT("%02x%02x%02x%02x"), Digest[0], Digest[1], Digest[2], Digest[3]);
    }

    UTexture2D* FindExistingTextureByHash(const FString& TargetDir, const FString& AssetName)
    {
        const FString FullPath = TargetDir / AssetName;
        UObject* Existing = UEditorAssetLibrary::LoadAsset(FullPath);
        return Cast<UTexture2D>(Existing);
    }
}

namespace WidgetClipboardTextureUtils
{
    UTexture2D* CreateOrReuseTextureFromPixels(const FClipboardImageData& ImageData, const FString& TargetDir)
    {
        const FString PixelHash = ComputePixelHash(ImageData.PixelData);
        const FString AssetName = FString::Printf(TEXT("T_Pasted_%s"), *PixelHash);

        if (UTexture2D* Existing = FindExistingTextureByHash(TargetDir, AssetName))
        {
            UE_LOG(LogAssetCustomsClipboardImport, Log, TEXT("Reusing existing texture: %s"), *Existing->GetPathName());
            return Existing;
        }

        const FString PackagePath = TargetDir / AssetName;

        UPackage* Package = CreatePackage(*PackagePath);
        if (!Package)
        {
            UE_LOG(LogAssetCustomsClipboardImport, Error, TEXT("Failed to create package: %s"), *PackagePath);
            return nullptr;
        }
        Package->FullyLoad();

        FImage SourceImage(ImageData.Width, ImageData.Height, ERawImageFormat::BGRA8, EGammaSpace::sRGB);
        if (SourceImage.RawData.Num() != ImageData.PixelData.Num())
        {
            UE_LOG(LogAssetCustomsClipboardImport, Error, TEXT("Pixel data size mismatch: expected %d, got %d"), SourceImage.RawData.Num(), ImageData.PixelData.Num());
            return nullptr;
        }
        FMemory::Memcpy(SourceImage.RawData.GetData(), ImageData.PixelData.GetData(), ImageData.PixelData.Num());

        UTexture* TextureBase = FImageUtils::CreateTexture(
            ETextureClass::TwoD,
            SourceImage,
            Package,
            AssetName,
            RF_Public | RF_Standalone,
            true);

        UTexture2D* Texture = Cast<UTexture2D>(TextureBase);
        if (!Texture)
        {
            UE_LOG(LogAssetCustomsClipboardImport, Error, TEXT("FImageUtils::CreateTexture failed for %s"), *AssetName);
            return nullptr;
        }

        Texture->LODGroup = TEXTUREGROUP_UI;
        Texture->CompressionSettings = TC_EditorIcon;
        Texture->MipGenSettings = TMGS_NoMipmaps;
        Texture->NeverStream = true;
        Texture->PostEditChange();

        FAssetRegistryModule::AssetCreated(Texture);

        FSavePackageArgs SaveArgs;
        SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
        const FString PackageFilename = FPackageName::LongPackageNameToFilename(PackagePath, FPackageName::GetAssetPackageExtension());
        const bool bSaved = UPackage::SavePackage(Package, Texture, *PackageFilename, SaveArgs);
        if (!bSaved)
        {
            UE_LOG(LogAssetCustomsClipboardImport, Warning, TEXT("Failed to save texture package to disk: %s"), *PackageFilename);
        }

        UE_LOG(LogAssetCustomsClipboardImport, Log, TEXT("Created texture: %s (%dx%d)"), *PackagePath, ImageData.Width, ImageData.Height);
        return Texture;
    }
}