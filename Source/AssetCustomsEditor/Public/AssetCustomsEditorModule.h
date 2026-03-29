#pragma once

#include "Modules/ModuleManager.h"

class IAssetEditorInstance;
class FSendToPhotoshopExtension;

class FAssetCustomsEditorModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;

private:
    void RegisterWidgetEditorMenu();
    void UnregisterWidgetEditorMenu();

    void RegisterWidgetContextMenuExtension();
    void UnregisterWidgetContextMenuExtension();

    /** Bind paste command to each Widget Blueprint Editor's toolkit commands. */
    void OnAssetOpenedInEditor(UObject* Asset, IAssetEditorInstance* EditorInstance);

    TSharedPtr<FExtender> WidgetMenuExtender;
    FDelegateHandle AssetOpenedDelegateHandle;

    TSharedPtr<FSendToPhotoshopExtension> SendToPhotoshopExtension;
};
