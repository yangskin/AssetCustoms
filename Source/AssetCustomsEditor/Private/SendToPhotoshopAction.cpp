#include "SendToPhotoshopAction.h"

#include "WidgetBlueprintEditor.h"
#include "WidgetReference.h"
#include "Components/Image.h"
#include "Styling/SlateBrush.h"
#include "IPythonScriptPlugin.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"

#define LOCTEXT_NAMESPACE "AssetCustomsEditor"

void FSendToPhotoshopExtension::ExtendContextMenu(
    FMenuBuilder& MenuBuilder,
    TSharedRef<FWidgetBlueprintEditor> BlueprintEditor,
    FVector2D TargetLocation) const
{
    // Check if exactly one Image widget is selected
    const TSet<FWidgetReference>& SelectedWidgets = BlueprintEditor->GetSelectedWidgets();
    if (SelectedWidgets.Num() != 1)
    {
        return;
    }

    const FWidgetReference& WidgetRef = *SelectedWidgets.CreateConstIterator();
    UWidget* Widget = WidgetRef.GetTemplate();
    UImage* ImageWidget = Cast<UImage>(Widget);
    if (!ImageWidget)
    {
        return;
    }

    const FSlateBrush& Brush = ImageWidget->GetBrush();
    UObject* ResourceObject = Brush.GetResourceObject();
    UTexture2D* Texture = Cast<UTexture2D>(ResourceObject);
    if (!Texture)
    {
        return;
    }

    FString AssetPath = Texture->GetPathName();

    MenuBuilder.BeginSection(TEXT("AssetCustomsPhotoshop"), LOCTEXT("PhotoshopSection", "AssetCustoms"));
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

                    // Escape backslashes for Python string
                    FString EscapedPath = AssetPath.Replace(TEXT("\\"), TEXT("\\\\"));
                    FString PythonCommand = FString::Printf(
                        TEXT("from unreal_integration.photoshop_bridge import PhotoshopBridge; PhotoshopBridge().open_texture_by_path_as_png('%s')"),
                        *EscapedPath);

                    PythonPlugin->ExecPythonCommand(*PythonCommand);
                })
            )
        );
    }
    MenuBuilder.EndSection();
}

#undef LOCTEXT_NAMESPACE
