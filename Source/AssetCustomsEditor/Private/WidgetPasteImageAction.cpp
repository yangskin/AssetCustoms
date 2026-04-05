#include "WidgetPasteImageAction.h"
#include "ClipboardImageUtils.h"
#include "WidgetClipboardTextureUtils.h"

#include "WidgetBlueprint.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Image.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/PanelWidget.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Misc/Guid.h"
#include "Misc/PackageName.h"
#include "Framework/Notifications/NotificationManager.h"
#include "Widgets/Notifications/SNotificationList.h"

DEFINE_LOG_CATEGORY_STATIC(LogAssetCustoms, Log, All);

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

    const FString WBPPackageName = WidgetBlueprint->GetOutermost()->GetName();
    const FString TargetDir = FPackageName::GetLongPackagePath(WBPPackageName);

    UTexture2D* Texture = WidgetClipboardTextureUtils::CreateOrReuseTextureFromPixels(ClipboardData, TargetDir);
    if (!Texture)
    {
        return;
    }

    UWidgetTree* WidgetTree = WidgetBlueprint->WidgetTree;
    if (!WidgetTree)
    {
        UE_LOG(LogAssetCustoms, Error, TEXT("PasteImage: WidgetTree is null"));
        return;
    }

    UCanvasPanel* TargetCanvas = nullptr;
    UPanelWidget* FallbackPanel = nullptr;

    WidgetTree->ForEachWidget([&](UWidget* Widget)
    {
        if (TargetCanvas)
        {
            return;
        }

        if (UCanvasPanel* Canvas = Cast<UCanvasPanel>(Widget))
        {
            TargetCanvas = Canvas;
        }
        else if (!FallbackPanel)
        {
            if (UPanelWidget* Panel = Cast<UPanelWidget>(Widget))
            {
                FallbackPanel = Panel;
            }
        }
    });

    if (!TargetCanvas && !FallbackPanel)
    {
        UE_LOG(LogAssetCustoms, Error, TEXT("PasteImage: No suitable panel found in widget tree"));
        ShowNotification(
            NSLOCTEXT("AssetCustoms", "NoPanelFound", "No Canvas Panel or other panel found in widget tree.\nAdd a panel widget first."));
        return;
    }

    const FString ImageName = FString::Printf(TEXT("IMG_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Short).Left(8));
    UImage* ImageWidget = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass(), *ImageName);
    if (!ImageWidget)
    {
        UE_LOG(LogAssetCustoms, Error, TEXT("PasteImage: Failed to construct Image widget"));
        return;
    }

    ImageWidget->SetBrushFromTexture(Texture, true);

    if (TargetCanvas)
    {
        UCanvasPanelSlot* Slot = TargetCanvas->AddChildToCanvas(ImageWidget);
        if (Slot)
        {
            Slot->SetAutoSize(true);
        }
    }
    else
    {
        FallbackPanel->AddChild(ImageWidget);
    }

    EnsureWidgetVariableGuids(WidgetBlueprint);
    WidgetBlueprint->MarkPackageDirty();

    if (!WidgetBlueprint->bBeingCompiled && WidgetBlueprint->Status != BS_BeingCreated)
    {
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBlueprint);
    }

    UE_LOG(LogAssetCustoms, Log, TEXT("PasteImage: Added Image '%s' with texture '%s' to '%s'"),
        *ImageName, *Texture->GetPathName(), *WidgetBlueprint->GetName());
}
