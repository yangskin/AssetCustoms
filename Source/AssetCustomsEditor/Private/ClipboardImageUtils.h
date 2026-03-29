#pragma once

#include "CoreMinimal.h"

struct FClipboardImageData
{
    TArray<uint8> PixelData; // BGRA8 pixel bytes
    int32 Width = 0;
    int32 Height = 0;
};

/**
 * Platform-specific clipboard image utilities.
 * Currently Windows-only (CF_DIB).
 */
namespace ClipboardImageUtils
{
    /** Check if the system clipboard contains an image. */
    bool HasClipboardImage();

    /** Grab image from system clipboard. Returns false if no image available. */
    bool GrabClipboardImage(FClipboardImageData& OutData);
}
