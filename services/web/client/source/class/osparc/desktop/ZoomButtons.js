/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that shows the zoom button.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let zoomButtons = new osparc.desktop.ZoomButtons();
 *   this.getRoot().add(zoomButtons);
 * </pre>
 */

const ZOOM_BUTTON_SIZE = 24;

qx.Class.define("osparc.desktop.ZoomButtons", {
  extend: qx.ui.toolbar.ToolBar,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(0));

    this.set({
      spacing: 0,
      backgroundColor: "transparent"
    });

    this.__buildLayout();
  },

  events: {
    "zoomIn": "qx.event.type.Event",
    "zoomOut": "qx.event.type.Event",
    "zoomReset": "qx.event.type.Event"
  },

  members: {
    __buildLayout: function() {
      this.add(this.__getZoomOutButton());
      this.add(this.__getZoomResetButton());
      this.add(this.__getZoomInButton());
    },

    __getZoomBtn: function(icon, tooltip) {
      const btn = new qx.ui.toolbar.Button(null, icon+"/20").set({
        width: ZOOM_BUTTON_SIZE,
        height: ZOOM_BUTTON_SIZE,
        backgroundColor: "transparent"
      });
      if (tooltip) {
        btn.setToolTipText(tooltip);
      }
      return btn;
    },

    __getZoomInButton: function() {
      const btn = this.__getZoomBtn("@MaterialIcons/zoom_in", this.tr("Zoom In"));
      btn.addListener("execute", () => this.fireEvent("zoomIn"), this);
      return btn;
    },

    __getZoomOutButton: function() {
      const btn = this.__getZoomBtn("@MaterialIcons/zoom_out", this.tr("Zoom Out"));
      btn.addListener("execute", () => this.fireEvent("zoomOut"), this);
      return btn;
    },

    __getZoomResetButton: function() {
      const btn = this.__getZoomBtn("@MaterialIcons/find_replace", this.tr("Reset Zoom"));
      btn.addListener("execute", () => this.fireEvent("zoomReset"), this);
      return btn;
    }
  }
});
