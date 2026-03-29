#pragma once

#include "IHasWidgetContextMenuExtensibility.h"

/**
 * Widget context menu extension: send selected Image widget's texture to Photoshop via Python.
 */
class FSendToPhotoshopExtension : public IWidgetContextMenuExtension
{
public:
    virtual void ExtendContextMenu(
        FMenuBuilder& MenuBuilder,
        TSharedRef<FWidgetBlueprintEditor> BlueprintEditor,
        FVector2D TargetLocation) const override;
};
