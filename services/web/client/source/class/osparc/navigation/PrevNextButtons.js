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
    },

    node: {
      check: "osparc.data.model.Node",
      apply: "__applyNode",
      nullable: false
    },

    nextState: {
      check: ["ready", "busy", "run", "select-file"],
      apply: "__updateNextButtonState",
      nullable: false,
      init: null
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
        icon: "@FontAwesome5Solid/arrow-left/32",
        ...this.self().BUTTON_OPTIONS
      });
      prvsBtn.addListener("execute", () => this.__prevPressed(), this);

      const nextBtn = this.__nextBtn = new qx.ui.form.Button().set({
        toolTipText: qx.locale.Manager.tr("Next"),
        icon: "@FontAwesome5Solid/arrow-right/32",
        ...this.self().BUTTON_OPTIONS
      });
      nextBtn.addListener("execute", () => this.__nextPressed(), this);
    },

    __applyStudy: function(study) {
      this.__updatePrevNextButtons();
      study.getUi().addListener("changeCurrentNodeId", () => this.__updatePrevNextButtons(), this);
    },

    __applyNode: function(node) {
      this.__updatePrevNextButtons();
      node.getStatus().addListener("changeRunning", () => this.__updatePrevNextButtons(), this);
      node.getStatus().addListener("changeOutput", () => this.__updatePrevNextButtons(), this);
    },

    __updateNextButtonState: function(state) {
      let icon = "@FontAwesome5Solid/arrow-right/32";
      let toolTipText = qx.locale.Manager.tr("Next");
      let textColor = "text";
      let animate = false;
      let enabled = true;
      switch (state) {
        case "run":
          icon = "@FontAwesome5Solid/play/32";
          toolTipText = qx.locale.Manager.tr("Run");
          break;
        case "select-file":
          icon = "@FontAwesome5Solid/file-medical/32";
          toolTipText = qx.locale.Manager.tr("Select File");
          enabled = false;
          break;
        case "busy":
          icon = "@FontAwesome5Solid/circle-notch/32";
          toolTipText = qx.locale.Manager.tr("Running");
          textColor = "busy-orange";
          animate = true;
          enabled = false;
          break;
      }
      if (this.__nextBtn) {
        this.__nextBtn.set({
          icon,
          toolTipText,
          textColor,
          enabled
        });
        const btnIcon = this.__nextBtn.getChildControl("icon").getContentElement();
        if (animate) {
          osparc.ui.basic.NodeStatusUI.addClass(btnIcon, "rotate");
        } else {
          osparc.ui.basic.NodeStatusUI.removeClass(btnIcon, "rotate");
        }
      }
    },

    __updatePrevNextButtons: function() {
      const studyUI = this.getStudy().getUi();
      const currentNodeId = studyUI.getCurrentNodeId();
      const nodesIds = studyUI.getSlideshow().getSortedNodeIds();
      const currentIdx = nodesIds.indexOf(currentNodeId);

      this.__prvsBtn.setEnabled(currentIdx > 0);
      // this.__nextBtn.setEnabled(currentIdx < nodesIds.length-1);

      const currentNode = this.getStudy().getWorkbench().getNode(nodesIds[currentIdx]);
      if (currentNode) {
        const currentNodeStatus = currentNode.getStatus();
        const currentNodeStatusOutput = currentNodeStatus.getOutput();
        if (["busy"].includes(currentNodeStatusOutput)) {
          this.setNextState("busy");
        } else if (currentNode.isFilePicker() && ["not-available"].includes(currentNodeStatusOutput)) {
          this.setNextState("select-file");
        } else if (currentNode.isComputational() && ["not-available", "out-of-date"].includes(currentNodeStatusOutput)) {
          this.setNextState("run");
        } else {
          this.setNextState("ready");
        }
      } else {
        this.setNextState("ready");
      }
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
