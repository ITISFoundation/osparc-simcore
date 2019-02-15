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
 * Widget containing a Vertical Box with a MainView and ControlsBar.
 * Used as Main View in the project editor.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let mainPanel = this.__mainPanel = new qxapp.desktop.MainPanel();
 *   mainPanel.setMainView(widget);
 *   this.getRoot().add(mainPanel);
 * </pre>
 */

/* eslint no-underscore-dangle: 0 */

qx.Class.define("qxapp.desktop.MainPanel", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    let hBox = this.__mainView = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
      allowGrowY: true
    });
    this._add(hBox, {
      flex: 1
    });

    let controlsBar = this.__controlsBar = new qxapp.desktop.ControlsBar();
    controlsBar.set({
      height: 60,
      allowGrowY: false
    });
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
