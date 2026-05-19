using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace ChaosOne.EditorScripts
{
    /// <summary>
    /// Headless build entry for Unity batchmode.
    ///
    /// Invoked from `unity/build.sh` or directly via:
    ///   Unity -batchmode -nographics -projectPath unity \
    ///         -executeMethod ChaosOne.EditorScripts.BuildPlayer.Run \
    ///         -buildOutput dist/ChaosOne.app
    ///         -buildTarget macOSUniversal
    ///         -quit
    ///
    /// Reads -buildOutput and -buildTarget from the command line. Builds
    /// every scene under EditorBuildSettings, or — if none are
    /// configured — every `*.unity` under `Assets/_ChaosOne/Scenes/`.
    /// </summary>
    public static class BuildPlayer
    {
        private const string DefaultOutput = "dist/ChaosOne";
        private const BuildTarget DefaultTarget = BuildTarget.StandaloneOSX;

        public static void Run()
        {
            var output = ReadArg("-buildOutput", DefaultOutput);
            var target = ParseBuildTarget(ReadArg("-buildTarget", "macOSUniversal"));

            var scenes = ResolveScenes();
            if (scenes.Length == 0)
            {
                Fail(
                    "no scenes found. Either configure scenes in File > Build Profiles > " +
                    "Scene List, or save a scene under Assets/_ChaosOne/Scenes/.");
                return;
            }

            Directory.CreateDirectory(Path.GetDirectoryName(output) ?? ".");

            var options = new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = ResolveOutputPath(output, target),
                target = target,
                options = BuildOptions.None,
            };

            Log($"building target {target} -> {options.locationPathName}");
            Log($"scenes ({scenes.Length}):");
            foreach (var scene in scenes) Log($"  {scene}");

            var report = BuildPipeline.BuildPlayer(options);
            if (report.summary.result == BuildResult.Succeeded)
            {
                Log($"build succeeded in {report.summary.totalTime}");
                EditorApplication.Exit(0);
            }
            else
            {
                Fail($"build {report.summary.result}: {report.summary.totalErrors} errors");
            }
        }

        private static string[] ResolveScenes()
        {
            var configured = new System.Collections.Generic.List<string>();
            foreach (var scene in EditorBuildSettings.scenes)
            {
                if (scene.enabled && !string.IsNullOrEmpty(scene.path)) configured.Add(scene.path);
            }
            if (configured.Count > 0) return configured.ToArray();

            var found = new System.Collections.Generic.List<string>();
            const string scenesRoot = "Assets/_ChaosOne/Scenes";
            if (Directory.Exists(scenesRoot))
            {
                foreach (var path in Directory.GetFiles(scenesRoot, "*.unity", SearchOption.AllDirectories))
                {
                    found.Add(path.Replace("\\", "/"));
                }
            }
            return found.ToArray();
        }

        private static string ResolveOutputPath(string baseOutput, BuildTarget target)
        {
            switch (target)
            {
                case BuildTarget.StandaloneOSX:
                    return baseOutput.EndsWith(".app") ? baseOutput : baseOutput + ".app";
                case BuildTarget.StandaloneWindows:
                case BuildTarget.StandaloneWindows64:
                    return baseOutput.EndsWith(".exe") ? baseOutput : baseOutput + ".exe";
                default:
                    return baseOutput;
            }
        }

        private static BuildTarget ParseBuildTarget(string raw)
        {
            switch (raw.ToLowerInvariant())
            {
                case "macos":
                case "macosx":
                case "macosuniversal":
                case "osxuniversal":
                case "standaloneosx":
                    return BuildTarget.StandaloneOSX;
                case "windows":
                case "windows64":
                case "win64":
                case "standalonewindows64":
                    return BuildTarget.StandaloneWindows64;
                case "linux":
                case "linux64":
                case "standalonelinux64":
                    return BuildTarget.StandaloneLinux64;
                default:
                    throw new ArgumentException($"unknown -buildTarget '{raw}'");
            }
        }

        private static string ReadArg(string name, string fallback)
        {
            var args = Environment.GetCommandLineArgs();
            for (var i = 0; i < args.Length - 1; i++)
            {
                if (string.Equals(args[i], name, StringComparison.Ordinal))
                {
                    return args[i + 1];
                }
            }
            return fallback;
        }

        private static void Log(string message) => Debug.Log($"[chaos-one build] {message}");

        private static void Fail(string message)
        {
            Debug.LogError($"[chaos-one build] {message}");
            EditorApplication.Exit(1);
        }
    }
}
