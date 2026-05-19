using System.Collections.Generic;
using System.IO;
using ChaosOne.Cameras;
using ChaosOne.Core;
using ChaosOne.Scenarios;
using ChaosOne.UI;
using Unity.Cinemachine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UIElements;

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

            BuildDemoTrack();

            var panelSettings = EnsurePanelSettings();
            BuildUIDocument<ModeHUD>("UI_ModeHUD", "Assets/_ChaosOne/UI/ModeHUD.uxml", panelSettings);
            BuildUIDocument<AdversaryMirror>("UI_AdversaryMirror", "Assets/_ChaosOne/UI/AdversaryMirror.uxml", panelSettings);
            BuildUIDocument<CalmChannel>("UI_CalmChannel", "Assets/_ChaosOne/UI/CalmChannel.uxml", panelSettings);
            BuildUIDocument<TrackInfoPanel>("UI_TrackInfoPanel", "Assets/_ChaosOne/UI/TrackInfoPanel.uxml", panelSettings);
            BuildDecisionsPanel(panelSettings);

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

        private static void BuildDemoTrack()
        {
            // A plain primitive sphere with a TrailRenderer so the camera
            // sees motion on launch. The real Stage pipeline replaces this
            // with ThreatTrack + TrackVisuals + envelope shader once a
            // ThreatArchetype.asset exists.
            var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            go.name = "DemoTrack";
            go.transform.localScale = new Vector3(160f, 160f, 160f);
            Object.DestroyImmediate(go.GetComponent<SphereCollider>());

            var renderer = go.GetComponent<MeshRenderer>();
            if (renderer != null)
            {
                renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            }

            var trail = go.AddComponent<TrailRenderer>();
            trail.time = 4f;
            trail.startWidth = 90f;
            trail.endWidth = 5f;
            trail.minVertexDistance = 8f;
            trail.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            trail.receiveShadows = false;

            var defaultLineMaterial = AssetDatabase.GetBuiltinExtraResource<Material>("Default-Line.mat");
            if (defaultLineMaterial != null)
            {
                trail.sharedMaterial = defaultLineMaterial;
            }

            go.AddComponent<DemoTrackMover>();
        }

        private const string PanelSettingsPath = "Assets/_ChaosOne/UI/PanelSettings.asset";

        private static PanelSettings EnsurePanelSettings()
        {
            var existing = AssetDatabase.LoadAssetAtPath<PanelSettings>(PanelSettingsPath);
            if (existing != null) return existing;

            var dir = Path.GetDirectoryName(PanelSettingsPath);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir)) Directory.CreateDirectory(dir);

            var panel = ScriptableObject.CreateInstance<PanelSettings>();
            AssetDatabase.CreateAsset(panel, PanelSettingsPath);
            AssetDatabase.SaveAssets();
            Debug.Log($"[auto-scene] created {PanelSettingsPath}");
            return panel;
        }

        private static GameObject BuildUIDocument<TController>(string name, string uxmlPath, PanelSettings panel)
            where TController : MonoBehaviour
        {
            var go = new GameObject(name);
            var doc = go.AddComponent<UIDocument>();
            doc.panelSettings = panel;

            var uxml = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(uxmlPath);
            if (uxml == null)
            {
                Debug.LogWarning($"[auto-scene] UXML not found at {uxmlPath} — UI surface will be empty");
            }
            else
            {
                doc.visualTreeAsset = uxml;
            }

            go.AddComponent<TController>();
            return go;
        }

        private static void BuildDecisionsPanel(PanelSettings panel)
        {
            var go = BuildUIDocument<DecisionsPanel>(
                "UI_DecisionsPanel",
                "Assets/_ChaosOne/UI/DecisionsPanel.uxml",
                panel);

            var coaCardUxml = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>("Assets/_ChaosOne/UI/COACard.uxml");
            if (coaCardUxml == null)
            {
                Debug.LogWarning("[auto-scene] COACard.uxml not found — DecisionsPanel will not render cards");
                return;
            }

            var decisions = go.GetComponent<DecisionsPanel>();
            var so = new SerializedObject(decisions);
            var prop = so.FindProperty("coaCardTemplate");
            if (prop != null)
            {
                prop.objectReferenceValue = coaCardUxml;
                so.ApplyModifiedPropertiesWithoutUndo();
            }
            else
            {
                Debug.LogWarning("[auto-scene] DecisionsPanel.coaCardTemplate field not found");
            }
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
