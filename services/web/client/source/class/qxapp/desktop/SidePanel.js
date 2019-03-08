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
 * Widget containing a Vertical Box with three widgets equaly sized.
 * Used for the side panel in the project editor.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let sidePanel = new qxapp.desktop.SidePanel();
 *   sidePanel.setTopView(widget1);
 *   sidePanel.setMidView(widget2);
 *   sidePanel.setBottomView(widget3);
 *   this.getRoot().add(sidePanel);
 * </pre>
 */

qx.Class.define("qxapp.desktop.SidePanel", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(0, null, "separator-vertical"));

    let topView = new qxapp.desktop.PanelView(this.tr("Service tree"));
    let midView = new qxapp.desktop.PanelView(this.tr("Overview"));
    let bottomView = new qxapp.desktop.PanelView(this.tr("Logger"));

    // panel.setContent(new qx.ui.basic.Label('Integer consectetur mi nec lectus elementum, in maximus dui tristique. Phasellus nec urna nec massa venenatis lacinia sit amet non lectus. Suspendisse sit amet dui malesuada, tincidunt ligula ut, ornare magna. Nullam erat quam, fringilla tempus eleifend ornare, pharetra molestie lectus. Pellentesque ac nibh vitae dui commodo sollicitudin. Fusce in nibh eu urna imperdiet efficitur ut vitae diam. Sed non sem quis justo aliquam tempus suscipit et tortor.')
    //   .set({ rich: true }));

    this._add(topView);
    this._add(midView);
    this._add(bottomView, {
      flex: 1
    });
  },

  properties: {
    topView: {
      nullable: false,
      check : "qx.ui.core.Widget",
      apply : "__applyTopView"
    },

    midView: {
      nullable: false,
      check : "qx.ui.core.Widget",
      apply : "__applyMidView"
    },

    bottomView: {
      nullable: false,
      check : "qx.ui.core.Widget",
      apply : "__applyBottomView"
    }
  },

  events: {},

  members: {
    __applyTopView: function(newWidget) {
      this._getChildren()[0].setContent(newWidget);
    },

    __applyMidView: function(newWidget) {
      this._getChildren()[1].setContent(newWidget);
    },

    __applyBottomView: function(newWidget) {
      this._getChildren()[2].setContent(newWidget);
    },

    __replaceWidgetAt: function(newWidget, indexOf) {
      if (this._indexOf(newWidget) !== indexOf) {
        this._removeAt(indexOf);
        this._addAt(newWidget, indexOf);
      }
    }
  }
});
