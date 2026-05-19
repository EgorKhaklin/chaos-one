using ChaosOne.Decisions;
using ChaosOne.Audit;
using ChaosOne.Net;
using ChaosOne.Scenarios;
using UnityEngine;

namespace ChaosOne.Core
{
    /// <summary>
    /// Single drop-in component that materializes the non-UI Chaos One
    /// services as named child GameObjects. Place one SceneBootstrap in a
    /// scene and every component below is created and registered in the
    /// ServiceRegistry at Awake. UI components (ModeHUD, DecisionsPanel,
    /// AdversaryMirror, CalmChannel, AuditReelView) still need their
    /// UIDocument and VisualTreeAsset wired in the Inspector since UI
    /// Toolkit requires the asset references at edit time.
    /// </summary>
    public sealed class SceneBootstrap : MonoBehaviour
    {
        [Header("Optional overrides")]
        [SerializeField] private ROEEnvelope roeEnvelope;
        [SerializeField] private bool spawnAuditLog = true;
        [SerializeField] private bool spawnBackendBootstrap = true;
        [SerializeField] private bool spawnDemoEventDriver = true;
        [SerializeField] private BackendMode backendMode = BackendMode.Scripted;

        private void Awake()
        {
            var modeStateMachine = SpawnChild<ModeStateMachine>("ModeStateMachine");
            var coaQueue = SpawnChild<COAQueue>("COAQueue");
            SpawnChild<AdversaryMirrorService>("AdversaryMirrorService");

            if (roeEnvelope != null && coaQueue != null)
            {
                BindROEEnvelope(coaQueue);
            }

            if (spawnAuditLog)
            {
                SpawnChild<AuditLogWriter>("AuditLogWriter");
            }

            if (spawnBackendBootstrap)
            {
                var go = new GameObject("BackendBootstrap");
                go.transform.SetParent(transform, worldPositionStays: false);
                var bootstrap = go.AddComponent<BackendBootstrap>();
                SetBackendMode(bootstrap);
            }

            if (spawnDemoEventDriver)
            {
                var go = new GameObject("DemoEventDriver");
                go.transform.SetParent(transform, worldPositionStays: false);
                var driver = go.AddComponent<DemoEventDriver>();
                BindDemoDriver(driver, modeStateMachine, coaQueue);
            }
        }

        private T SpawnChild<T>(string name) where T : MonoBehaviour
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, worldPositionStays: false);
            return go.AddComponent<T>();
        }

        private void BindROEEnvelope(COAQueue queue)
        {
            var envelopeField = typeof(COAQueue).GetField(
                "envelope",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            envelopeField?.SetValue(queue, roeEnvelope);
        }

        private void SetBackendMode(BackendBootstrap bootstrap)
        {
            var modeField = typeof(BackendBootstrap).GetField(
                "mode",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            modeField?.SetValue(bootstrap, backendMode);
        }

        private void BindDemoDriver(DemoEventDriver driver, ModeStateMachine modeStateMachine, COAQueue coaQueue)
        {
            var modeField = typeof(DemoEventDriver).GetField(
                "modeStateMachine",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            modeField?.SetValue(driver, modeStateMachine);

            var queueField = typeof(DemoEventDriver).GetField(
                "coaQueue",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            queueField?.SetValue(driver, coaQueue);
        }
    }
}
