using ChaosOne.Core;
using UnityEngine;

namespace ChaosOne.Threats
{
    /// <summary>
    /// Owns the visual representation of one ThreatTrack: trail color
    /// gradient driven by altitude + state, and envelope shader uniforms
    /// driven by track state and confidence. Subscribes to TrackUpdated and
    /// TrackStateChanged events filtered to its own track.
    /// </summary>
    [RequireComponent(typeof(ThreatTrack))]
    public sealed class TrackVisuals : MonoBehaviour
    {
        [Header("Envelope")]
        [SerializeField] private Renderer envelopeRenderer;
        [SerializeField] private float disagreementStripeCount = 14f;

        [Header("Trail")]
        [SerializeField] private TrailRenderer trailRenderer;
        [SerializeField] private Gradient confidentGradient;
        [SerializeField] private Gradient candidateGradient;
        [SerializeField] private Gradient disagreementGradient;
        [SerializeField] private Gradient lostGradient;

        private static readonly int BaseColorId = Shader.PropertyToID("_BaseColor");
        private static readonly int ConfidenceId = Shader.PropertyToID("_Confidence");
        private static readonly int DisagreementId = Shader.PropertyToID("_DisagreementStripes");
        private static readonly int StateTintId = Shader.PropertyToID("_StateTint");
        private static readonly int EmissiveId = Shader.PropertyToID("_EmissiveIntensity");

        private ThreatTrack track;
        private MaterialPropertyBlock propertyBlock;

        private void Awake()
        {
            track = GetComponent<ThreatTrack>();
            propertyBlock = new MaterialPropertyBlock();
        }

        private void OnEnable()
        {
            ApplyForState(track.State, confidence: 0.6f);
            EventBus.Subscribe<TrackUpdated>(OnTrackUpdated);
            EventBus.Subscribe<TrackStateChanged>(OnTrackStateChanged);
        }

        private void OnDisable()
        {
            EventBus.Unsubscribe<TrackUpdated>(OnTrackUpdated);
            EventBus.Unsubscribe<TrackStateChanged>(OnTrackStateChanged);
        }

        private void OnTrackUpdated(TrackUpdated evt)
        {
            if (evt.Track != track) return;
            ApplyForState(track.State, evt.Sample.Confidence);
        }

        private void OnTrackStateChanged(TrackStateChanged evt)
        {
            if (evt.Track != track) return;
            ApplyForState(evt.Current, track.LatestSample.Confidence);
        }

        private void ApplyForState(TrackState state, float confidence)
        {
            ApplyEnvelopeUniforms(state, confidence);
            ApplyTrailGradient(state);
        }

        private void ApplyEnvelopeUniforms(TrackState state, float confidence)
        {
            if (envelopeRenderer == null) return;
            if (track.Archetype == null) return;

            propertyBlock.Clear();
            propertyBlock.SetColor(BaseColorId, track.Archetype.EnvelopeBaseColor);
            propertyBlock.SetFloat(ConfidenceId, Mathf.Clamp01(confidence));
            propertyBlock.SetFloat(DisagreementId, state == TrackState.EnsembleDisagreement ? disagreementStripeCount : 0f);
            propertyBlock.SetColor(StateTintId, TintFor(state));
            propertyBlock.SetFloat(EmissiveId, state == TrackState.Lost ? 0.5f : 2.5f);

            envelopeRenderer.SetPropertyBlock(propertyBlock);
            envelopeRenderer.enabled = state != TrackState.Lost;
        }

        private void ApplyTrailGradient(TrackState state)
        {
            if (trailRenderer == null) return;

            var gradient = state switch
            {
                TrackState.ConfidentRV => confidentGradient,
                TrackState.CandidateDecoy => candidateGradient,
                TrackState.EnsembleDisagreement => disagreementGradient,
                TrackState.Lost => lostGradient,
                _ => confidentGradient,
            };

            if (gradient != null)
            {
                trailRenderer.colorGradient = gradient;
            }
        }

        private static Color TintFor(TrackState state) => state switch
        {
            TrackState.ConfidentRV => new Color(1f, 1f, 1f),
            TrackState.CandidateDecoy => new Color(0.92f, 0.86f, 0.78f),
            TrackState.EnsembleDisagreement => new Color(1.10f, 0.85f, 0.55f),
            TrackState.Engaged => new Color(1.20f, 0.65f, 0.45f),
            TrackState.Lost => new Color(0.45f, 0.45f, 0.50f),
            _ => Color.white,
        };
    }
}
