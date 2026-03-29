#include "AssetCustomsEditorModule.h"
#include "WidgetPasteImageAction.h"
#include "SendToPhotoshopAction.h"

#include "WidgetBlueprintEditor.h"
#include "WidgetBlueprint.h"
#include "UMGEditorModule.h"
#include "IHasWidgetContextMenuExtensibility.h"
#include "Framework/Commands/Commands.h"
#include "Framework/Commands/UICommandList.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "Styling/AppStyle.h"
#include "Toolkits/BaseToolkit.h"

#define LOCTEXT_NAMESPACE "AssetCustomsEditor"

/**
 * UI command definitions for AssetCustoms editor actions.
 */
class FAssetCustomsCommands : public TCommands<FAssetCustomsCommands>
{
public:
    FAssetCustomsCommands()
        : TCommands<FAssetCustomsCommands>(
            TEXT("AssetCustomsEditor"),
            LOCTEXT("AssetCustomsEditorCommands", "AssetCustoms Editor"),
            NAME_None,
            FAppStyle::GetAppStyleSetName())
    {
    }

    virtual void RegisterCommands() override
    {
        UI_COMMAND(PasteImageFromClipboard,
            "Paste Image from Clipboard",
            "Paste clipboard image as a new Image widget with auto-imported texture",
            EUserInterfaceActionType::Button,
            FInputChord(EModifierKey::Control | EModifierKey::Shift, EKeys::V));
    }

    TSharedPtr<FUICommandInfo> PasteImageFromClipboard;
};

/**
 * Find the currently active Widget Blueprint being edited.
 */
static UWidgetBlueprint* GetActiveWidgetBlueprint()
{
    UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
    if (!AssetEditorSubsystem)
    {
        return nullptr;
    }

    TArray<UObject*> EditedAssets = AssetEditorSubsystem->GetAllEditedAssets();
    for (UObject* Asset : EditedAssets)
    {
        UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(Asset);
        if (WidgetBP)
        {
            IAssetEditorInstance* Editor = AssetEditorSubsystem->FindEditorForAsset(Asset, false);
            if (Editor)
            {
                return WidgetBP;
            }
        }
    }

    return nullptr;
}

static void ExecutePasteImageCommand()
{
    UWidgetBlueprint* WidgetBP = GetActiveWidgetBlueprint();
    if (WidgetBP)
    {
        WidgetPasteImageAction::Execute(WidgetBP);
    }
}

void FAssetCustomsEditorModule::StartupModule()
{
    FAssetCustomsCommands::Register();
    RegisterWidgetEditorMenu();
    RegisterWidgetContextMenuExtension();

    // Bind shortcut to each Widget Blueprint Editor as it opens
    if (GEditor)
    {
        UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
        if (AssetEditorSubsystem)
        {
            AssetOpenedDelegateHandle = AssetEditorSubsystem->OnAssetOpenedInEditor().AddRaw(
                this, &FAssetCustomsEditorModule::OnAssetOpenedInEditor);
        }
    }
}

void FAssetCustomsEditorModule::ShutdownModule()
{
    if (GEditor)
    {
        UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
        if (AssetEditorSubsystem && AssetOpenedDelegateHandle.IsValid())
        {
            AssetEditorSubsystem->OnAssetOpenedInEditor().Remove(AssetOpenedDelegateHandle);
        }
    }

    UnregisterWidgetContextMenuExtension();
    UnregisterWidgetEditorMenu();
    FAssetCustomsCommands::Unregister();
}

void FAssetCustomsEditorModule::OnAssetOpenedInEditor(UObject* Asset, IAssetEditorInstance* EditorInstance)
{
    UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(Asset);
    if (!WidgetBP || !EditorInstance)
    {
        return;
    }

    FWidgetBlueprintEditor* WBEditor = static_cast<FWidgetBlueprintEditor*>(EditorInstance);
    const TSharedRef<FUICommandList>& ToolkitCommands = WBEditor->GetToolkitCommands();

    // Only bind if not already mapped (editor may reuse instance)
    if (!ToolkitCommands->IsActionMapped(FAssetCustomsCommands::Get().PasteImageFromClipboard))
    {
        ToolkitCommands->MapAction(
            FAssetCustomsCommands::Get().PasteImageFromClipboard,
            FExecuteAction::CreateStatic(&ExecutePasteImageCommand),
            FCanExecuteAction::CreateLambda([]() { return true; }));
    }
}

void FAssetCustomsEditorModule::RegisterWidgetEditorMenu()
{
    // Create command list and bind the paste action
    TSharedRef<FUICommandList> CommandList = MakeShared<FUICommandList>();
    CommandList->MapAction(
        FAssetCustomsCommands::Get().PasteImageFromClipboard,
        FExecuteAction::CreateStatic(&ExecutePasteImageCommand),
        FCanExecuteAction::CreateLambda([]() { return true; }));

    // Create menu extender for Widget Blueprint editor
    WidgetMenuExtender = MakeShared<FExtender>();
    WidgetMenuExtender->AddMenuExtension(
        TEXT("EditHistory"),
        EExtensionHook::After,
        CommandList,
        FMenuExtensionDelegate::CreateLambda([](FMenuBuilder& MenuBuilder)
        {
            MenuBuilder.BeginSection(TEXT("AssetCustomsPaste"), LOCTEXT("AssetCustomsPasteSection", "AssetCustoms"));
            {
                MenuBuilder.AddMenuEntry(FAssetCustomsCommands::Get().PasteImageFromClipboard);
            }
            MenuBuilder.EndSection();
        }));

    // Register with UMGEditor module's extensibility manager
    if (FModuleManager::Get().IsModuleLoaded(TEXT("UMGEditor")))
    {
        IUMGEditorModule& UMGEditorModule = FModuleManager::GetModuleChecked<IUMGEditorModule>(TEXT("UMGEditor"));
        TSharedPtr<FExtensibilityManager> MenuExtManager = UMGEditorModule.GetMenuExtensibilityManager();
        if (MenuExtManager.IsValid())
        {
            MenuExtManager->AddExtender(WidgetMenuExtender);
        }
    }
    else
    {
        FModuleManager::Get().OnModulesChanged().AddLambda(
            [this](FName ModuleName, EModuleChangeReason Reason)
            {
                if (ModuleName == TEXT("UMGEditor") && Reason == EModuleChangeReason::ModuleLoaded
                    && WidgetMenuExtender.IsValid())
                {
                    IUMGEditorModule& UMGEditorModule = FModuleManager::GetModuleChecked<IUMGEditorModule>(TEXT("UMGEditor"));
                    TSharedPtr<FExtensibilityManager> MenuExtManager = UMGEditorModule.GetMenuExtensibilityManager();
                    if (MenuExtManager.IsValid())
                    {
                        MenuExtManager->AddExtender(WidgetMenuExtender);
                    }
                }
            });
    }
}

void FAssetCustomsEditorModule::UnregisterWidgetEditorMenu()
{
    if (WidgetMenuExtender.IsValid() && FModuleManager::Get().IsModuleLoaded(TEXT("UMGEditor")))
    {
        IUMGEditorModule& UMGEditorModule = FModuleManager::GetModuleChecked<IUMGEditorModule>(TEXT("UMGEditor"));
        TSharedPtr<FExtensibilityManager> MenuExtManager = UMGEditorModule.GetMenuExtensibilityManager();
        if (MenuExtManager.IsValid())
        {
            MenuExtManager->RemoveExtender(WidgetMenuExtender);
        }
    }
    WidgetMenuExtender.Reset();
}

void FAssetCustomsEditorModule::RegisterWidgetContextMenuExtension()
{
    SendToPhotoshopExtension = MakeShared<FSendToPhotoshopExtension>();

    if (FModuleManager::Get().IsModuleLoaded(TEXT("UMGEditor")))
    {
        IUMGEditorModule& UMGEditorModule = FModuleManager::GetModuleChecked<IUMGEditorModule>(TEXT("UMGEditor"));
        UMGEditorModule.GetWidgetContextMenuExtensibilityManager()->AddExtension(SendToPhotoshopExtension.ToSharedRef());
    }
    else
    {
        FModuleManager::Get().OnModulesChanged().AddLambda(
            [this](FName ModuleName, EModuleChangeReason Reason)
            {
                if (ModuleName == TEXT("UMGEditor") && Reason == EModuleChangeReason::ModuleLoaded
                    && SendToPhotoshopExtension.IsValid())
                {
                    IUMGEditorModule& UMGEditorModule = FModuleManager::GetModuleChecked<IUMGEditorModule>(TEXT("UMGEditor"));
                    UMGEditorModule.GetWidgetContextMenuExtensibilityManager()->AddExtension(SendToPhotoshopExtension.ToSharedRef());
                }
            });
    }
}

void FAssetCustomsEditorModule::UnregisterWidgetContextMenuExtension()
{
    if (SendToPhotoshopExtension.IsValid() && FModuleManager::Get().IsModuleLoaded(TEXT("UMGEditor")))
    {
        IUMGEditorModule& UMGEditorModule = FModuleManager::GetModuleChecked<IUMGEditorModule>(TEXT("UMGEditor"));
        UMGEditorModule.GetWidgetContextMenuExtensibilityManager()->RemoveExtension(SendToPhotoshopExtension.ToSharedRef());
    }
    SendToPhotoshopExtension.Reset();
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FAssetCustomsEditorModule, AssetCustomsEditor)
