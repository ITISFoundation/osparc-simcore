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
    "takeSnapshot": "qx.event.type.Event",
    "convertToStudy": "qx.event.type.Event",
    "showSnapshots": "qx.event.type.Event",
    "openPrimaryStudy": "qx.event.type.Data"
  },

  members: {
    __navNodes: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "breadcrumb-navigation": {
          const breadcrumbNavigation = this.__navNodes = new osparc.navigation.BreadcrumbsWorkbench();
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
        case "take-snapshot-btn": {
          control = new osparc.ui.form.FetchButton(this.tr("Take Snapshot")).set({
            icon: "@FontAwesome5Solid/code-branch/14",
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
            allowGrowX: false
          });
          control.addListener("execute", () => {
            this.fireDataEvent("takeSnapshot");
          }, this);
          this._add(control);
          break;
        }
        case "convert-to-study-btn": {
          control = new osparc.ui.form.FetchButton(this.tr("Convert To Study")).set({
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
            allowGrowX: false
          });
          control.addListener("execute", () => {
            this.fireDataEvent("convertToStudy");
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
      }
      return control || this.base(arguments, id);
    },

    // overriden
    _buildLayout: function() {
      this.getChildControl("breadcrumb-navigation");

      this._add(new qx.ui.core.Spacer(20));

      const takeSnapshotBtn = this.getChildControl("take-snapshot-btn");
      takeSnapshotBtn.exclude();

      const snapshotsBtn = this.getChildControl("snapshots-btn");
      snapshotsBtn.exclude();

      const startStopBtns = this._startStopBtns = this.getChildControl("start-stop-btns");
      startStopBtns.exclude();
    },

    // overriden
    _populateNodesNavigationLayout: function() {
      const study = this.getStudy();
      if (study) {
        const nodeIds = study.getWorkbench().getPathIds(study.getUi().getCurrentNodeId());
        this.__navNodes.populateButtons(nodeIds);

        const takeSnapshotBtn = this.getChildControl("take-snapshot-btn");
        takeSnapshotBtn.setVisibility(osparc.data.Permissions.getInstance().canDo("study.snapshot.create") ? "visible" : "excluded");

        study.getWorkbench().addListener("nNodesChanged", this.evalSnapshotsBtn, this);
        this.evalSnapshotsBtn();
      }
    },

    evalSnapshotsBtn: async function() {
      const study = this.getStudy();
      if (study) {
        const hasSnapshots = await study.hasSnapshots();
        const snapshotsBtn = this.getChildControl("snapshots-btn");
        hasSnapshots ? snapshotsBtn.show() : snapshotsBtn.exclude();
      }
    },

    __attachEventHandlers: function() {
      qx.event.message.Bus.subscribe("changeWorkbenchSelection", e => {
        const selectedNodes = e.getData();
        const selectedNodeIds = [];
        selectedNodes.forEach(selectedNode => {
          selectedNodeIds.push(selectedNode.getNodeId());
        });
        this.getStartStopButtons().nodeSelectionChanged(selectedNodeIds);
      }, this);
    }
  }
});
