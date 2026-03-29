#pragma once

#include "CoreMinimal.h"

class UWidgetBlueprint;

/**
 * Handles the "Paste Image from Clipboard" action in Widget Blueprint Editor.
 * Creates a Texture2D asset from clipboard pixels, then adds an Image widget.
 * Texture is saved to the same directory as the Widget Blueprint.
 * Duplicate clipboard content is detected via pixel hash — reuses existing texture.
 */
namespace WidgetPasteImageAction
{
    /** Execute the paste action on the given Widget Blueprint. */
    void Execute(UWidgetBlueprint* WidgetBlueprint);
}
