using ChaosOne.Core;
using UnityEngine;
using UnityEngine.InputSystem;

namespace ChaosOne.Threats
{
    /// <summary>
    /// Translates pointer clicks into track-selection events. Attach to a
    /// GameObject in the scene and assign the active camera. Tracks must
    /// carry a collider on a child or self to be hit by the raycast.
    /// </summary>
    public sealed class ThreatTrackSelector : MonoBehaviour
    {
        [SerializeField] private Camera selectionCamera;
        [SerializeField] private LayerMask selectionMask = ~0;
        [SerializeField] private float maxDistance = 5_000_000f;

        private ThreatTrack currentSelection;

        private void Reset()
        {
            selectionCamera = Camera.main;
        }

        private void Update()
        {
            var mouse = Mouse.current;
            if (mouse == null) return;
            if (!mouse.leftButton.wasPressedThisFrame) return;
            if (selectionCamera == null) return;

            var screen = mouse.position.ReadValue();
            var ray = selectionCamera.ScreenPointToRay(screen);

            if (Physics.Raycast(ray, out var hit, maxDistance, selectionMask, QueryTriggerInteraction.Collide))
            {
                var track = hit.collider.GetComponentInParent<ThreatTrack>();
                if (track != null)
                {
                    Select(track);
                    return;
                }
            }

            Deselect();
        }

        public void Select(ThreatTrack track)
        {
            if (currentSelection == track) return;

            if (currentSelection != null)
            {
                EventBus.Publish(new TrackDeselected(currentSelection));
            }

            currentSelection = track;
            EventBus.Publish(new TrackSelected(track));
        }

        public void Deselect()
        {
            if (currentSelection == null) return;
            EventBus.Publish(new TrackDeselected(currentSelection));
            currentSelection = null;
        }
    }
}
