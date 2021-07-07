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

qx.Class.define("osparc.desktop.WorkbenchToolbar", {
  extend: osparc.desktop.Toolbar,

  construct: function() {
    this.base(arguments);

    this.__attachEventHandlers();
  },

  events: {
    "showParameters": "qx.event.type.Event",
    "showSnapshots": "qx.event.type.Event",
    "openPrimaryStudy": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "breadcrumb-navigation": {
          const breadcrumbNavigation = this._navNodes = new osparc.navigation.BreadcrumbsWorkbench();
          breadcrumbNavigation.addListener("nodeSelected", e => {
            this.fireDataEvent("nodeSelected", e.getData());
          }, this);
          control = new qx.ui.container.Scroll();
          control.add(breadcrumbNavigation);
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "parameters-btn": {
          control = new qx.ui.form.Button(this.tr("Parameters")).set({
            icon: "@FontAwesome5Solid/sliders-h/14",
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
            allowGrowX: false
          });
          control.addListener("execute", () => {
            this.fireDataEvent("showParameters");
          }, this);
          this._add(control);
          break;
        }
        case "snapshots-btn": {
          control = new qx.ui.form.Button(this.tr("Snapshots")).set({
            icon: "@FontAwesome5Solid/copy/14",
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
            allowGrowX: false
          });
          control.addListener("execute", () => {
            this.fireDataEvent("showSnapshots");
          }, this);
          this._add(control);
          break;
        }
        case "primary-study-btn": {
          control = new qx.ui.form.Button(this.tr("Open Main Study")).set({
            icon: "@FontAwesome5Solid/external-link-alt/14",
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
            allowGrowX: false
          });
          control.addListener("execute", () => {
            const primaryStudyId = this.getStudy().getSweeper().getPrimaryStudyId();
            if (primaryStudyId) {
              this.fireDataEvent("openPrimaryStudy", primaryStudyId);
            }
          }, this);
          this._add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    // overriden
    _buildLayout: function() {
      this.getChildControl("breadcrumb-navigation");

      this._add(new qx.ui.core.Spacer(20));

      const primaryBtn = this.getChildControl("primary-study-btn");
      primaryBtn.exclude();

      /*
      const sweeperBtn = this.getChildControl("parameters-btn");
      sweeperBtn.exclude();
      osparc.data.model.Sweeper.isSweeperEnabled()
        .then(isSweeperEnabled => {
          if (isSweeperEnabled) {
            sweeperBtn.show();
          }
        });
      */

      const snapshotsBtn = this.getChildControl("snapshots-btn");
      snapshotsBtn.exclude();
      osparc.data.model.Sweeper.isSweeperEnabled()
        .then(isSweeperEnabled => {
          if (isSweeperEnabled) {
            snapshotsBtn.show();
          }
        });

      this._startStopBtns = this.getChildControl("start-stop-btns");
    },

    // overriden
    _populateNodesNavigationLayout: function() {
      const study = this.getStudy();
      if (study) {
        const nodeIds = study.getWorkbench().getPathIds(study.getUi().getCurrentNodeId());
        this._navNodes.populateButtons(nodeIds, "slash");

        const primaryBtn = this.getChildControl("primary-study-btn");
        primaryBtn.setVisibility(study.isSnapshot() ? "visible" : "excluded");

        const sweeperBtn = this.getChildControl("parameters-btn");
        sweeperBtn.setVisibility(study.isSnapshot() ? "excluded" : "visible");

        const snapshotsBtn = this.getChildControl("snapshots-btn");
        snapshotsBtn.setVisibility(study.isSnapshot() ? "excluded" : "visible");

        study.getWorkbench().addListener("nNodesChanged", () => {
          const allNodes = study.getWorkbench().getNodes(true);
          const isSweepeable = Object.values(allNodes).some(node => node.isIterator());
          snapshotsBtn.setEnabled(isSweepeable);
          sweeperBtn.setEnabled(isSweepeable);
        }, this);
      }
    },

    __workbenchSelectionChanged: function(msg) {
      const selectedNodes = msg.getData();
      this.getStartStopButtons().nodeSelectionChanged(selectedNodes);
    },

    __attachEventHandlers: function() {
      qx.event.message.Bus.subscribe("changeWorkbenchSelection", this.__workbenchSelectionChanged, this);
    }
  }
});
