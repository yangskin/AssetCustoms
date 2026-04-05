#pragma once

class FWidgetBlueprintEditor;

namespace WidgetReplaceTextureFromClipboardAction
{
    bool CanExecute(const FWidgetBlueprintEditor* BlueprintEditor);
    void Execute(FWidgetBlueprintEditor* BlueprintEditor);
}