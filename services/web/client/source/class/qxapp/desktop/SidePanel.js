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

    this._setLayout(new qx.ui.layout.VBox(10, null, "separator-vertical"));

    let topView = new qx.ui.core.Widget();
    let midView = new qx.ui.core.Widget();
    let bottomView = new qx.ui.core.Widget();

    this._add(topView, {
      height: "33%",
      flex: 1
    });
    this._add(midView, {
      height: "33%",
      flex: 1
    });
    this._add(bottomView, {
      height: "33%",
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
      this.__replaceWidgetAt(newWidget, 0);
    },

    __applyMidView: function(newWidget) {
      this.__replaceWidgetAt(newWidget, 1);
    },

    __applyBottomView: function(newWidget) {
      this.__replaceWidgetAt(newWidget, 2);
    },

    __replaceWidgetAt: function(newWidget, indexOf) {
      if (this._indexOf(newWidget) !== indexOf) {
        this._removeAt(indexOf);
        this._addAt(newWidget, indexOf, {
          height: "33%",
          flex: 1
        });
      }
    }
  }
});
