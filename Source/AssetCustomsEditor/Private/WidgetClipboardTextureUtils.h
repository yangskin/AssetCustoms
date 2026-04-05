#pragma once

#include "CoreMinimal.h"

struct FClipboardImageData;

class UTexture2D;

namespace WidgetClipboardTextureUtils
{
    UTexture2D* CreateOrReuseTextureFromPixels(const FClipboardImageData& ImageData, const FString& TargetDir);
}