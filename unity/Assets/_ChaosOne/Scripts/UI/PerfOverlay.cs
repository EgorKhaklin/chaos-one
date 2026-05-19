using System.Text;
using ChaosOne.Threats;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Profiling;

namespace ChaosOne.UI
{
    /// <summary>
    /// Toggle-able dev overlay. F1 cycles visibility. Shows current frame
    /// rate, used/total memory, active track count, and a frame-time mean
    /// over a short rolling window. Off by default; never shown in shipping
    /// builds unless explicitly enabled.
    /// </summary>
    public sealed class PerfOverlay : MonoBehaviour
    {
        [SerializeField] private bool visibleOnStart;
        [SerializeField] private Vector2 anchorPx = new(16f, 64f);
        [SerializeField] private int frameSampleWindow = 60;

        private readonly float[] frameSamples = new float[120];
        private int frameSampleIndex;
        private float frameSampleAccumulator;
        private bool visible;
        private GUIStyle guiStyle;
        private readonly StringBuilder builder = new(256);

        private void Awake()
        {
            visible = visibleOnStart;
            for (var i = 0; i < frameSamples.Length; i++) frameSamples[i] = Time.deltaTime;
            frameSampleAccumulator = Time.deltaTime * frameSamples.Length;
        }

        private void Update()
        {
            var keyboard = Keyboard.current;
            if (keyboard != null && keyboard.f1Key.wasPressedThisFrame)
            {
                visible = !visible;
            }

            var window = Mathf.Clamp(frameSampleWindow, 8, frameSamples.Length);
            frameSampleAccumulator -= frameSamples[frameSampleIndex];
            frameSamples[frameSampleIndex] = Time.unscaledDeltaTime;
            frameSampleAccumulator += frameSamples[frameSampleIndex];
            frameSampleIndex = (frameSampleIndex + 1) % window;
        }

        private void OnGUI()
        {
            if (!visible) return;

            guiStyle ??= new GUIStyle(GUI.skin.label)
            {
                fontSize = 12,
                fontStyle = FontStyle.Bold,
                normal = { textColor = new Color(0.92f, 0.89f, 0.82f, 1f) },
            };

            var window = Mathf.Clamp(frameSampleWindow, 8, frameSamples.Length);
            var meanDt = frameSampleAccumulator / window;
            var fps = meanDt > 1e-6f ? 1f / meanDt : 0f;

            var allocatedMb = Profiler.GetTotalAllocatedMemoryLong() / (1024f * 1024f);
            var reservedMb = Profiler.GetTotalReservedMemoryLong() / (1024f * 1024f);

            var trackCount = FindObjectsByType<ThreatTrack>(FindObjectsSortMode.None).Length;

            builder.Clear();
            builder.Append("PERF\n");
            builder.AppendFormat("  fps     {0,5:F0}\n", fps);
            builder.AppendFormat("  dt mean {0,5:F1} ms\n", meanDt * 1000f);
            builder.AppendFormat("  alloc   {0,5:F0} / {1,5:F0} MiB\n", allocatedMb, reservedMb);
            builder.AppendFormat("  tracks  {0,5}\n", trackCount);
            builder.Append("  (F1 to hide)");

            var width = 220f;
            var height = 110f;
            GUI.Box(new Rect(anchorPx.x, anchorPx.y, width, height), GUIContent.none);
            GUI.Label(new Rect(anchorPx.x + 8f, anchorPx.y + 6f, width - 16f, height - 12f), builder.ToString(), guiStyle);
        }
    }
}
