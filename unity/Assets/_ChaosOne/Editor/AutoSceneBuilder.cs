using System.Collections.Generic;
using System.IO;
using ChaosOne.Cameras;
using ChaosOne.Core;
using ChaosOne.UI;
using Unity.Cinemachine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace ChaosOne.EditorScripts
{
    /// <summary>
    /// Programmatically constructs the minimum Battlespace.unity scene
    /// so the project builds to a runnable Unity player without any
    /// manual scene authoring in the Editor.
    ///
    /// What gets created:
    ///   Main Camera     Camera + CinemachineBrain, deep navy clear color.
    ///   Directional Light  default warm key.
    ///   VCam_SideAltitude  CinemachineCamera with priority 100.
    ///   CinemachineDirector  wires the vcam through the runtime director.
    ///   ChaosOne        SceneBootstrap (spawns all non-UI services on
    ///                   Awake) + PerfOverlay (F1 toggle).
    ///
    /// UI Toolkit documents (Mode HUD, Decisions Panel, etc.) are NOT
    /// wired up here. They require PanelSettings + theme references
    /// that vary by project state and shouldn't be invented by a build
    /// script. Run the .app for an empty-but-functional battlespace,
    /// then add the UI surfaces from the Unity Editor when ready.
    ///
    /// Invocable from Editor menu (Chaos One > Build Battlespace Scene)
    /// or from CLI:
    ///   Unity -batchmode -quit -projectPath unity \
    ///         -executeMethod ChaosOne.EditorScripts.AutoSceneBuilder.Create
    /// </summary>
    public static class AutoSceneBuilder
    {
        public const string ScenePath = "Assets/_ChaosOne/Scenes/Battlespace.unity";

        [MenuItem("Chaos One/Build Battlespace Scene")]
        public static void Create()
        {
            EnsureScenesDirectory();

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            BuildCamera();
            BuildLight();
            var vcam = BuildCinemachineCamera();
            BuildCinemachineDirector(vcam);
            BuildChaosOneRoot();

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, ScenePath);
            Debug.Log($"[auto-scene] saved {ScenePath}");

            RegisterInBuildSettings();
            AssetDatabase.SaveAssets();
            Debug.Log("[auto-scene] done");
        }

        private static void BuildCamera()
        {
            var go = new GameObject("Main Camera");
            go.tag = "MainCamera";
            var camera = go.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.039f, 0.086f, 0.157f, 1f);
            camera.nearClipPlane = 0.1f;
            camera.farClipPlane = 50_000f;
            camera.fieldOfView = 45f;
            go.transform.position = new Vector3(0f, 1500f, -8000f);
            go.transform.rotation = Quaternion.Euler(8f, 0f, 0f);

            go.AddComponent<CinemachineBrain>();

            go.AddComponent<AudioListener>();
        }

        private static void BuildLight()
        {
            var go = new GameObject("Directional Light");
            var light = go.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.1f;
            light.color = new Color(1.00f, 0.95f, 0.85f);
            light.shadows = LightShadows.Soft;
            go.transform.rotation = Quaternion.Euler(45f, -30f, 0f);
        }

        private static CinemachineCamera BuildCinemachineCamera()
        {
            var go = new GameObject("VCam_SideAltitude");
            var vcam = go.AddComponent<CinemachineCamera>();
            vcam.Priority = 100;
            go.transform.position = new Vector3(0f, 1500f, -8000f);
            go.transform.rotation = Quaternion.Euler(8f, 0f, 0f);
            return vcam;
        }

        private static void BuildCinemachineDirector(CinemachineCamera sideAltitudeVcam)
        {
            var go = new GameObject("CinemachineDirector");
            var director = go.AddComponent<CinemachineDirector>();

            // The vcam fields are private serialized fields; assign them via
            // SerializedObject so changes persist with the scene save.
            var so = new SerializedObject(director);
            AssignField(so, "sideAltitudeCam", sideAltitudeVcam);
            so.ApplyModifiedPropertiesWithoutUndo();

            go.AddComponent<CameraInputController>();
        }

        private static void BuildChaosOneRoot()
        {
            var go = new GameObject("ChaosOne");
            go.AddComponent<SceneBootstrap>();
            go.AddComponent<PerfOverlay>();
        }

        private static void RegisterInBuildSettings()
        {
            var scenes = new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
            var alreadyPresent = scenes.Exists(s => s.path == ScenePath);
            if (alreadyPresent)
            {
                return;
            }
            scenes.Add(new EditorBuildSettingsScene(ScenePath, enabled: true));
            EditorBuildSettings.scenes = scenes.ToArray();
            Debug.Log("[auto-scene] registered scene in EditorBuildSettings");
        }

        private static void AssignField(SerializedObject so, string fieldName, Object value)
        {
            var prop = so.FindProperty(fieldName);
            if (prop == null)
            {
                Debug.LogWarning($"[auto-scene] field '{fieldName}' not found");
                return;
            }
            prop.objectReferenceValue = value;
        }

        private static void EnsureScenesDirectory()
        {
            var dir = Path.GetDirectoryName(ScenePath);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
            {
                Directory.CreateDirectory(dir);
            }
        }
    }
}
