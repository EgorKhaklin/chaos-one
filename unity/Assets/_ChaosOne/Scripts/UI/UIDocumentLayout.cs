using UnityEngine.UIElements;

namespace ChaosOne.UI
{
    /// <summary>
    /// Utility for the M2 UI surfaces. By default a UIDocument's root
    /// visual element is laid out as a block child of the panel root,
    /// which means the absolute-positioned panel classes inside resolve
    /// against the wrong containing block (and every UIDocument lands
    /// in the top-left corner stacked on top of the others). Calling
    /// FillPanel(doc) in OnEnable() pins the UIDocument's root to all
    /// four edges of the panel and turns off pointer interception on
    /// the wrapper, restoring the per-panel absolute layout.
    /// </summary>
    public static class UIDocumentLayout
    {
        public static void FillPanel(UIDocument document)
        {
            if (document == null) return;
            var root = document.rootVisualElement;
            if (root == null) return;
            root.style.position = Position.Absolute;
            root.style.left = 0;
            root.style.top = 0;
            root.style.right = 0;
            root.style.bottom = 0;
            root.pickingMode = PickingMode.Ignore;
        }
    }
}
