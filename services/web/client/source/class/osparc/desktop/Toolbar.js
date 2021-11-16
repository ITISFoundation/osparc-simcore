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

qx.Class.define("osparc.desktop.Toolbar", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10).set({
      alignY: "middle"
    }));
    this.setAppearance("sidepanel");

    this.set({
      paddingLeft: 6,
      paddingRight: 6,
      height: 46
    });

    this._buildLayout();
  },

  events: {
    "nodeSelected": "qx.event.type.Data",
    "startPipeline": "qx.event.type.Event",
    "startPartialPipeline": "qx.event.type.Event",
    "stopPipeline": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "_applyStudy",
      nullable: false
    }
  },

  members: {
    _startStopBtns: null,

    getStartStopButtons: function() {
      return this._startStopBtns;
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "start-stop-btns": {
          control = new osparc.desktop.StartStopButtons();
          [
            "startPipeline",
            "startPartialPipeline",
            "stopPipeline"
          ].forEach(signalName => {
            control.addListener(signalName, () => {
              this.fireEvent(signalName);
            }, this);
          });
          this._add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _applyStudy: function(study) {
      if (study) {
        study.getUi().addListener("changeCurrentNodeId", () => {
          this._populateNodesNavigationLayout();
        });
        this._startStopBtns.setStudy(study);

        this._populateNodesNavigationLayout();
      }
    },

    _buildLayout: function() {
      throw new Error("Abstract method called!");
    },

    _populateNodesNavigationLayout: function() {
      throw new Error("Abstract method called!");
    }
  }
});
