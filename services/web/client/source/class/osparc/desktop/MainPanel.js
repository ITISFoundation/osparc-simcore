/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* eslint no-underscore-dangle: 0 */

/**
 * Widget containing a Vertical Box with a MainView and ControlsBar.
 * Used as Main View in the study editor.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let mainPanel = this.__mainPanel = new osparc.desktop.MainPanel();
 *   mainPanel.setMainView(widget);
 *   this.getRoot().add(mainPanel);
 * </pre>
 */

qx.Class.define("osparc.desktop.MainPanel", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    const hBox = this.__mainView = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
      allowGrowY: true
    });
    this._add(hBox, {
      flex: 1
    });

    const controlsBar = this.__controlsBar = new osparc.desktop.ControlsBar();
    this._add(controlsBar);
  },

  properties: {
    mainView: {
      nullable: false,
      check : "qx.ui.core.Widget",
      apply : "__applyMainView"
    }
  },

  members: {
    __mainView: null,
    __controlsBar: null,

    __applyMainView: function(newWidget) {
      this.__mainView.removeAll();
      this.__mainView.add(newWidget, {
        flex: 1
      });
    },

    getControls: function() {
      return this.__controlsBar;
    }
  }
});
