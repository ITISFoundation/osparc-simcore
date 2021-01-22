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

qx.Class.define("osparc.desktop.SlideShowToolbar", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10).set({
      alignY: "middle"
    }));
    this.setAppearance("sidepanel");

    this.__buildLayout();
  },

  events: {
    "nodeSelected": "qx.event.type.Data",
    "startPipeline": "qx.event.type.Event",
    "stopPipeline": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "_applyStudy",
      init: null,
      nullable: false
    }
  },

  members: {
    __navNodes: null,
    __prevNextBtns: null,
    __startStopBtns: null,

    getStartButton: function() {
      return this.__startStopBtns.getStartButton();
    },

    getStopButton: function() {
      return this.__startStopBtns.getStopButton();
    },

    _applyStudy: function(study) {
      if (study) {
        study.getUi().addListener("changeCurrentNodeId", () => {
          this.__populateGuidedNodesLayout();
        });
        this.__startStopBtns.setVisibility(study.isReadOnly() ? "excluded" : "visible");

        this.__populateGuidedNodesLayout();
      }
    },

    __buildLayout: function() {
      this.getChildControl("breadcrumb-navigation");
      this.__prevNextBtns = this.getChildControl("prev-next-btns");

      this._add(new qx.ui.core.Spacer(20));

      this.__startStopBtns = this.getChildControl("start-stop-btns");
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "breadcrumb-navigation": {
          control = new qx.ui.container.Scroll();
          const breadcrumbNavigation = this.__navNodes = new osparc.navigation.BreadcrumbNavigation();
          breadcrumbNavigation.addListener("nodeSelected", e => {
            this.fireDataEvent("nodeSelected", e.getData());
          }, this);
          control.add(breadcrumbNavigation);
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "prev-next-btns": {
          control = new osparc.navigation.PrevNextButtons();
          control.addListener("nodeSelected", e => {
            this.fireDataEvent("nodeSelected", e.getData());
          }, this);
          this._add(control);
          break;
        }
        case "start-stop-btns": {
          control = new osparc.desktop.StartStopButtons();
          control.addListener("startPipeline", () => {
            this.fireEvent("startPipeline");
          }, this);
          control.addListener("stopPipeline", () => {
            this.fireEvent("stopPipeline");
          }, this);
          this._add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __populateGuidedNodesLayout: function() {
      const study = this.getStudy();
      if (study) {
        const slideShow = study.getUi().getSlideshow();
        const nodes = [];
        for (let nodeId in slideShow) {
          const node = slideShow[nodeId];
          nodes.push({
            ...node,
            nodeId
          });
        }
        nodes.sort((a, b) => (a.position > b.position) ? 1 : -1);
        const nodeIds = [];
        nodes.forEach(node => {
          nodeIds.push(node.nodeId);
        });

        this.__navNodes.populateButtons(nodeIds, "arrow");
        this.__prevNextBtns.populateButtons(nodeIds);
      }
    },

    __workbenchSelectionChanged: function(msg) {
      const selectedNodes = msg.getData();
      if (!this.getStartButton().isFetching()) {
        if (selectedNodes.length) {
          this.getStartButton().setLabel(this.tr("Run selection"));
        } else {
          this.getStartButton().setLabel(this.tr("Run"));
        }
      }
    },

    __attachEventHandlers: function() {
      qx.event.message.Bus.subscribe("changeWorkbenchSelection", this.__workbenchSelectionChanged, this);
    }
  }
});
