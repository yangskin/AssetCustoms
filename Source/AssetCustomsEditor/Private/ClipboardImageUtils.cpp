#include "ClipboardImageUtils.h"

#if PLATFORM_WINDOWS
#include "Windows/AllowWindowsPlatformTypes.h"
#include <Windows.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

bool ClipboardImageUtils::HasClipboardImage()
{
#if PLATFORM_WINDOWS
    return ::IsClipboardFormatAvailable(CF_DIB) || ::IsClipboardFormatAvailable(CF_DIBV5);
#else
    return false;
#endif
}

bool ClipboardImageUtils::GrabClipboardImage(FClipboardImageData& OutData)
{
#if PLATFORM_WINDOWS
    if (!::OpenClipboard(nullptr))
    {
        return false;
    }

    // Prefer CF_DIBV5 (supports alpha), fall back to CF_DIB
    UINT Format = CF_DIBV5;
    HGLOBAL GlobalMem = ::GetClipboardData(CF_DIBV5);
    if (!GlobalMem)
    {
        Format = CF_DIB;
        GlobalMem = ::GetClipboardData(CF_DIB);
    }

    if (!GlobalMem)
    {
        ::CloseClipboard();
        return false;
    }

    const uint8* Data = static_cast<const uint8*>(::GlobalLock(GlobalMem));
    if (!Data)
    {
        ::CloseClipboard();
        return false;
    }

    bool bSuccess = false;

    // Parse BITMAPINFOHEADER (works for both CF_DIB and CF_DIBV5)
    const BITMAPINFOHEADER* Header = reinterpret_cast<const BITMAPINFOHEADER*>(Data);
    const int32 Width = Header->biWidth;
    const int32 Height = FMath::Abs(Header->biHeight);
    const bool bTopDown = (Header->biHeight < 0);
    const int32 BitCount = Header->biBitCount;

    if (Width > 0 && Height > 0 && (BitCount == 24 || BitCount == 32))
    {
        // Calculate offset to pixel data
        int32 HeaderSize = Header->biSize;
        // Skip color table for BI_BITFIELDS only if header is BITMAPINFOHEADER (40 bytes).
        // BITMAPV5HEADER (124 bytes) already includes mask fields in the struct.
        if (Header->biCompression == BI_BITFIELDS && Header->biSize <= sizeof(BITMAPINFOHEADER))
        {
            HeaderSize += 3 * sizeof(DWORD);
        }

        const uint8* PixelStart = Data + HeaderSize;
        const int32 SrcStride = ((Width * BitCount + 31) / 32) * 4; // DWORD-aligned

        OutData.Width = Width;
        OutData.Height = Height;
        OutData.PixelData.SetNumUninitialized(Width * Height * 4);

        for (int32 Y = 0; Y < Height; ++Y)
        {
            // DIB is bottom-up by default; flip unless top-down
            const int32 SrcY = bTopDown ? Y : (Height - 1 - Y);
            const uint8* SrcRow = PixelStart + SrcY * SrcStride;
            uint8* DstRow = OutData.PixelData.GetData() + Y * Width * 4;

            for (int32 X = 0; X < Width; ++X)
            {
                if (BitCount == 32)
                {
                    // BGRA already
                    DstRow[X * 4 + 0] = SrcRow[X * 4 + 0]; // B
                    DstRow[X * 4 + 1] = SrcRow[X * 4 + 1]; // G
                    DstRow[X * 4 + 2] = SrcRow[X * 4 + 2]; // R
                    DstRow[X * 4 + 3] = SrcRow[X * 4 + 3]; // A
                }
                else // 24-bit
                {
                    DstRow[X * 4 + 0] = SrcRow[X * 3 + 0]; // B
                    DstRow[X * 4 + 1] = SrcRow[X * 3 + 1]; // G
                    DstRow[X * 4 + 2] = SrcRow[X * 3 + 2]; // R
                    DstRow[X * 4 + 3] = 255;                // A (opaque)
                }
            }
        }

        bSuccess = true;
    }

    ::GlobalUnlock(GlobalMem);
    ::CloseClipboard();

    return bSuccess;
#else
    return false;
#endif
}
