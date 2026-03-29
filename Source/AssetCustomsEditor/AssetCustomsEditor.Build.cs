// AssetCustoms Editor Module — C++ editor extensions (Widget paste image, etc.)

using UnrealBuildTool;

public class AssetCustomsEditor : ModuleRules
{
    public AssetCustomsEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicIncludePaths.AddRange(new string[]
        {
            System.IO.Path.Combine(ModuleDirectory, "Public"),
        });

        PrivateIncludePaths.AddRange(new string[]
        {
            System.IO.Path.Combine(ModuleDirectory, "Private"),
        });

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "Slate",
            "SlateCore",
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "UnrealEd",
            "UMG",
            "UMGEditor",
            "Kismet",
            "ImageCore",
            "EditorScriptingUtilities",
            "AssetRegistry",
            "ApplicationCore",
            "InputCore",
        });
    }
}
