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

qx.Class.define("osparc.navigation.PrevNextButtons", {
  extend: qx.core.Object,

  construct: function() {
    this.base(arguments);

    this.__createButtons();
  },

  events: {
    "nodeSelected": "qx.event.type.Data"
  },

  statics: {
    BUTTON_OPTIONS: {
      backgroundColor: "background-main",
      allowGrowX: false,
      allowGrowY: false
    }
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "__applyStudy",
      nullable: false
    }
  },

  members: {
    __prvsBtn: null,
    __nextBtn: null,

    getPreviousButton: function() {
      return this.__prvsBtn;
    },

    getNextButton: function() {
      return this.__nextBtn;
    },

    __createButtons: function() {
      const prvsBtn = this.__prvsBtn = new qx.ui.form.Button().set({
        toolTipText: qx.locale.Manager.tr("Previous"),
        icon: "@FontAwesome5Solid/arrow-left/24",
        ...this.self().BUTTON_OPTIONS
      });
      prvsBtn.addListener("execute", () => this.__prevPressed(), this);

      const nextBtn = this.__nextBtn = new qx.ui.form.Button().set({
        toolTipText: qx.locale.Manager.tr("Next"),
        icon: "@FontAwesome5Solid/arrow-right/24",
        ...this.self().BUTTON_OPTIONS
      });
      nextBtn.addListener("execute", () => this.__nextPressed(), this);
    },

    __applyStudy: function(study) {
      this.__updatePrevNextButtons();
      study.getUi().addListener("changeCurrentNodeId", () => this.__updatePrevNextButtons(), this);
    },

    __updatePrevNextButtons: function() {
      const studyUI = this.getStudy().getUi();
      const currentNodeId = studyUI.getCurrentNodeId();
      const nodesIds = studyUI.getSlideshow().getSortedNodeIds();
      const currentIdx = nodesIds.indexOf(currentNodeId);

      this.__prvsBtn.setEnabled(currentIdx > 0);
      this.__nextBtn.setEnabled(currentIdx < nodesIds.length-1);
    },

    __prevPressed: function() {
      const studyUI = this.getStudy().getUi();
      const currentNodeId = studyUI.getCurrentNodeId();
      const nodesIds = studyUI.getSlideshow().getSortedNodeIds();
      const currentIdx = nodesIds.indexOf(currentNodeId);

      this.fireDataEvent("nodeSelected", nodesIds[currentIdx-1]);
    },

    __nextPressed: function() {
      const studyUI = this.getStudy().getUi();
      const currentNodeId = studyUI.getCurrentNodeId();
      const nodesIds = studyUI.getSlideshow().getSortedNodeIds();
      const currentIdx = nodesIds.indexOf(currentNodeId);

      this.fireDataEvent("nodeSelected", nodesIds[currentIdx+1]);
    }
  }
});
