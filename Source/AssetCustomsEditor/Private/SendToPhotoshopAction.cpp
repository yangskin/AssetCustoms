#include "../Public/SendToPhotoshopAction.h"

#include "ClipboardImageUtils.h"
#include "WidgetReplaceTextureFromClipboardAction.h"

#include "Components/Image.h"
#include "Engine/Texture2D.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "IPythonScriptPlugin.h"
#include "Styling/SlateBrush.h"
#include "WidgetBlueprintEditor.h"
#include "WidgetReference.h"

#define LOCTEXT_NAMESPACE "AssetCustomsEditor"

namespace
{
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

        const FSlateBrush& Brush = OutImage->GetBrush();
        OutTexture = Cast<UTexture2D>(Brush.GetResourceObject());
        return true;
    }
}

void FSendToPhotoshopExtension::ExtendContextMenu(
    FMenuBuilder& MenuBuilder,
    TSharedRef<FWidgetBlueprintEditor> BlueprintEditor,
    FVector2D TargetLocation) const
{
    UImage* ImageWidget = nullptr;
    UTexture2D* Texture = nullptr;
    if (!TryGetSelectedImage(&BlueprintEditor.Get(), ImageWidget, Texture))
    {
        return;
    }

    const FString AssetPath = Texture ? Texture->GetPathName() : FString();
    TWeakPtr<FWidgetBlueprintEditor> WeakBlueprintEditor(BlueprintEditor);

    MenuBuilder.BeginSection(TEXT("AssetCustomsPhotoshop"), LOCTEXT("PhotoshopSection", "AssetCustoms"));
    {
        MenuBuilder.AddMenuEntry(
            LOCTEXT("ReplaceTextureFromClipboard", "Replace Texture from Clipboard"),
            LOCTEXT("ReplaceTextureFromClipboardTooltip", "Reimport the selected Image's texture from the clipboard, or create and assign a texture when the brush is empty"),
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateLambda([WeakBlueprintEditor]()
                {
                    TSharedPtr<FWidgetBlueprintEditor> PinnedBlueprintEditor = WeakBlueprintEditor.Pin();
                    if (PinnedBlueprintEditor.IsValid())
                    {
                        WidgetReplaceTextureFromClipboardAction::Execute(PinnedBlueprintEditor.Get());
                    }
                }),
                FCanExecuteAction::CreateLambda([]()
                {
                    return ClipboardImageUtils::HasClipboardImage();
                })
            )
        );

        if (Texture)
        {
            MenuBuilder.AddMenuEntry(
                LOCTEXT("SendToPhotoshop", "Send to Photoshop (PNG)"),
                LOCTEXT("SendToPhotoshopTooltip", "Export this Image's texture as PNG and open in Photoshop"),
                FSlateIcon(),
                FUIAction(
                    FExecuteAction::CreateLambda([AssetPath]()
                    {
                        IPythonScriptPlugin* PythonPlugin = IPythonScriptPlugin::Get();
                        if (!PythonPlugin || !PythonPlugin->IsPythonAvailable())
                        {
                            UE_LOG(LogTemp, Warning, TEXT("PythonScriptPlugin is not available"));
                            return;
                        }

                        const FString EscapedPath = AssetPath.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("'"), TEXT("\\'"));
                        const FString PythonCommand = FString::Printf(
                            TEXT("from unreal_integration.photoshop_bridge import PhotoshopBridge; PhotoshopBridge().open_texture_by_path_as_png('%s')"),
                            *EscapedPath);

                        if (!PythonPlugin->ExecPythonCommand(*PythonCommand))
                        {
                            UE_LOG(LogTemp, Warning, TEXT("SendToPhotoshop: Python command failed for '%s'"), *AssetPath);
                        }
                    })
                )
            );
        }
    }
    MenuBuilder.EndSection();
}

#undef LOCTEXT_NAMESPACE
