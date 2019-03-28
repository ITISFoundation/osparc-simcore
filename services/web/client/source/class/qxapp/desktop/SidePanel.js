/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget containing a Vertical Box with widgets.
 * Used for the side panel in the project editor.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let sidePanel = new qxapp.desktop.SidePanel();
 *   sidePanel.addAt(widget1, 0);
 *   sidePanel.addAt(widget2, 1);
 *   sidePanel.addAt(widget3, 2);
 *   this.getRoot().add(sidePanel);
 * </pre>
 */

qx.Class.define("qxapp.desktop.SidePanel", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments);

    this.setAppearance("sidebar");

    this._setLayout(new qx.ui.layout.VBox());
  },

  members: {
    /**
     * Add a widget at the specified index. If the index already has a child, then replace it.
     *
     * @param {qx.ui.core.LayoutItem} child Widget to add
     * @param {Integer} index Index, at which the widget will be inserted
     * @param {Map?null} options Optional layout data for widget.
     */
    addOrReplaceAt: function(child, index, options = null) {
      if (this.getChildren()[index]) {
        this.removeAt(index);
      }
      this.addAt(child, index, options);
    }
  }
});
