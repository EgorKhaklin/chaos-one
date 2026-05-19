using ChaosOne.Core;
using ChaosOne.Decisions;
using UnityEngine;
using UnityEngine.InputSystem;

namespace ChaosOne.UI
{
    /// <summary>
    /// Keyboard bindings for the Decisions Panel hot loop:
    ///   Enter   authorize top (recommended) COA
    ///   O       object to top COA
    /// Keys map onto the same actions the on-screen buttons trigger so the
    /// operator can stay keyboard-first during a hot engagement.
    /// </summary>
    public sealed class DecisionsHotkeys : MonoBehaviour
    {
        private void Update()
        {
            if (!ServiceRegistry.TryResolve<COAQueue>(out var queue)) return;
            if (queue.ActiveCoas.Count == 0) return;

            var top = ResolveTop(queue);
            if (top == null) return;

            var keyboard = Keyboard.current;
            if (keyboard == null) return;

            if (keyboard.enterKey.wasPressedThisFrame)
            {
                queue.Authorize(top.Id, AuthorizationSource.Operator);
            }
            else if (keyboard.oKey.wasPressedThisFrame)
            {
                queue.Object(top.Id, "hotkey objection");
            }
        }

        private static CourseOfAction ResolveTop(COAQueue queue)
        {
            CourseOfAction recommended = null;
            CourseOfAction first = null;
            foreach (var coa in queue.ActiveCoas)
            {
                first ??= coa;
                if (coa.IsRecommended) { recommended = coa; break; }
            }
            return recommended ?? first;
        }
    }
}
