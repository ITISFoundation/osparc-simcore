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
    "nodeSelected": "qx.event.type.Data",
    "runPressed": "qx.event.type.Data"
  },

  statics: {
    BUTTON_OPTIONS: {
      backgroundColor: "background-main-1",
      allowGrowX: false,
      allowGrowY: false
    },

    PREV_BUTTON: "@FontAwesome5Solid/arrow-left/32",
    NEXT_BUTTON: "@FontAwesome5Solid/arrow-right/32",
    RUN_BUTTON: "@FontAwesome5Solid/play/32",
    BUSY_BUTTON: "@FontAwesome5Solid/circle-notch/32",
    SELECT_FILE_BUTTON: "@FontAwesome5Solid/file-medical/32"
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
    }
  },

  members: {
    __prvsBtn: null,
    __nextBtn: null,
    __runBtn: null,

    getPreviousButton: function() {
      return this.__prvsBtn;
    },

    getNextButton: function() {
      return this.__nextBtn;
    },

    getRunButton: function() {
      return this.__runBtn;
    },

    __createButtons: function() {
      const prvsBtn = this.__prvsBtn = new qx.ui.form.Button().set({
        toolTipText: qx.locale.Manager.tr("Previous"),
        icon: this.self().PREV_BUTTON,
        ...this.self().BUTTON_OPTIONS
      });
      osparc.utils.Utils.setIdToWidget(prvsBtn, "AppMode_PreviousBtn");
      prvsBtn.addListener("execute", () => this.__prevPressed(), this);

      const nextBtn = this.__nextBtn = new qx.ui.form.Button().set({
        toolTipText: qx.locale.Manager.tr("Next"),
        icon: this.self().NEXT_BUTTON,
        ...this.self().BUTTON_OPTIONS
      });
      osparc.utils.Utils.setIdToWidget(nextBtn, "AppMode_NextBtn");
      nextBtn.addListener("execute", () => this.__nextPressed(), this);

      const runBtn = this.__runBtn = new qx.ui.form.Button().set({
        toolTipText: qx.locale.Manager.tr("Run"),
        icon: this.self().RUN_BUTTON,
        ...this.self().BUTTON_OPTIONS
      });
      osparc.utils.Utils.setIdToWidget(runBtn, "AppMode_RunBtn");
      runBtn.addListener("execute", () => this.__runPressed(), this);
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

    __updatePrevNextButtons: function() {
      const studyUI = this.getStudy().getUi();
      const currentNodeId = studyUI.getCurrentNodeId();
      const nodesIds = studyUI.getSlideshow().getSortedNodeIds();
      const currentIdx = nodesIds.indexOf(currentNodeId);
      const isFirst = currentIdx === 0;
      const isLast = currentIdx === nodesIds.length-1;

      this.__prvsBtn.setEnabled(!isFirst);

      const currentNode = this.getStudy().getWorkbench().getNode(nodesIds[currentIdx]);
      this.__nextBtn.show();
      this.__runBtn.exclude();
      if (currentNode) {
        const currentNodeStatusOutput = currentNode.getStatus().getOutput();
        if (["busy"].includes(currentNodeStatusOutput)) {
          this.__updateNextButtonState("busy");
        } else if (currentNode.isFilePicker() && ["not-available"].includes(currentNodeStatusOutput)) {
          this.__updateNextButtonState("select-file");
        } else if (currentNode.isComputational() && ["not-available", "out-of-date"].includes(currentNodeStatusOutput)) {
          this.__nextBtn.exclude();
          this.__runBtn.show();
        } else {
          this.__updateNextButtonState("ready");
          this.__nextBtn.setEnabled(!isLast);
        }
      } else {
        this.__updateNextButtonState("ready");
      }
    },

    /*
     * @param state {String} "ready"|"busy"|"run"|"select-file"
     */
    __updateNextButtonState: function(state) {
      let icon = "";
      let toolTipText = "";
      let textColor = "text";
      let animate = false;
      let enabled = true;
      switch (state) {
        case "select-file":
          icon = this.self().SELECT_FILE_BUTTON;
          toolTipText = qx.locale.Manager.tr("Select File");
          enabled = false;
          break;
        case "busy":
          icon = this.self().BUSY_BUTTON;
          toolTipText = qx.locale.Manager.tr("Running");
          textColor = "busy-orange";
          animate = true;
          enabled = false;
          break;
        default:
          icon = this.self().NEXT_BUTTON;
          toolTipText = qx.locale.Manager.tr("Next");
          break;
      }
      if (this.__nextBtn) {
        this.__nextBtn.set({
          icon,
          toolTipText,
          textColor,
          enabled
        });
        // Hack: Show tooltip if button is disabled
        if (enabled) {
          this.__nextBtn.getContentElement().removeAttribute("title");
        } else {
          this.__nextBtn.getContentElement().setAttribute("title", toolTipText);
        }
        const btnIcon = this.__nextBtn.getChildControl("icon").getContentElement();
        if (animate) {
          osparc.utils.Utils.addClass(btnIcon, "rotate");
        } else {
          osparc.utils.Utils.removeClass(btnIcon, "rotate");
        }
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
    },

    __runPressed: function() {
      const nodeId = this.getNode().getNodeId();
      this.fireDataEvent("runPressed", nodeId);
    }
  }
});
