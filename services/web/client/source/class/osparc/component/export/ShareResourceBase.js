/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.component.export.ShareResourceBase", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  construct: function(studyId) {
    this.base(arguments);

    this._studyId = studyId;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  statics: {
    createWindow: function(winText, shareResourceWidget) {
      const window = new qx.ui.window.Window(winText).set({
        appearance: "service-window",
        layout: new qx.ui.layout.Grow(),
        autoDestroy: true,
        contentPadding: 0,
        width: 400,
        height: 300,
        showMaximize: false,
        showMinimize: false,
        modal: true
      });
      window.add(shareResourceWidget);
      window.center();
      return window;
    }
  },

  events: {
    "finished": "qx.event.type.Data"
  },

  properties: {
    headerText: {
      check: "String",
      init: "",
      event: "changeHeaderText"
    },

    buttonText: {
      check: "String",
      init: "",
      event: "changeButtonText"
    }
  },

  members: {
    _studyId: null,
    _shareWith: null,

    popUpWindow: function(winText) {
      const window = this.self().createWindow(winText, this);
      this.addListener("finished", e => {
        if (e.getData()) {
          window.close();
        }
      }, this);
      window.open();
    },

    __buildLayout: function() {
      const shareWith = this._shareWith = new osparc.component.export.ShareWith();
      this.bind("headerText", shareWith, "legend");
      this._add(shareWith, {
        flex: 1
      });

      const shareResourceBtn = new osparc.ui.form.FetchButton().set({
        allowGrowX: false,
        alignX: "right"
      });
      this.bind("buttonText", shareResourceBtn, "label");
      shareResourceBtn.addListener("execute", () => {
        this._shareResource(shareResourceBtn);
      }, this);
      shareWith.bind("ready", shareResourceBtn, "enabled");
      this._add(shareResourceBtn);
    },

    /**
      * @abstract
      */
    _shareResource: function(btn) {
      throw new Error("Abstract method called!");
    }
  }
});
