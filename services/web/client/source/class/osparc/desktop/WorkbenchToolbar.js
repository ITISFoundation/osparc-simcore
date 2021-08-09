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

      const takeSnapshotBtn = this.getChildControl("take-snapshot-btn");
      takeSnapshotBtn.exclude();

      const convertToStudy = this.getChildControl("convert-to-study-btn");
      convertToStudy.exclude();

      const primaryBtn = this.getChildControl("primary-study-btn");
      primaryBtn.exclude();

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
        this._navNodes.populateButtons(nodeIds, "slash");

        const takeSnapshotBtn = this.getChildControl("take-snapshot-btn");
        const convertToStudyBtn = this.getChildControl("convert-to-study-btn");
        const primaryBtn = this.getChildControl("primary-study-btn");
        if (study.isSnapshot()) {
          takeSnapshotBtn.exclude();
          convertToStudyBtn.show();
          primaryBtn.show();
        } else {
          takeSnapshotBtn.setVisibility(osparc.data.Permissions.getInstance().canDo("study.snapshot.create") ? "visible" : "excluded");
          convertToStudyBtn.exclude();
          primaryBtn.exclude();
        }

        study.getWorkbench().addListener("nNodesChanged", this.evalSnapshotsBtn, this);
        this.evalSnapshotsBtn();

        study.isSnapshot() ? this._startStopBtns.exclude() : this._startStopBtns.show();
      }
    },

    evalSnapshotsBtn: function() {
      const study = this.getStudy();
      if (study) {
        const allNodes = study.getWorkbench().getNodes(true);
        const hasIterators = Object.values(allNodes).some(node => node.isIterator());
        const isSnapshot = study.isSnapshot();
        const snapshotsBtn = this.getChildControl("snapshots-btn");
        (hasIterators && !isSnapshot) ? snapshotsBtn.show() : snapshotsBtn.exclude();
      }
    },

    __attachEventHandlers: function() {
      qx.event.message.Bus.subscribe("changeWorkbenchSelection", e => {
        const selectedNodes = e.getData();
        this.getStartStopButtons().nodeSelectionChanged(selectedNodes);
      }, this);
    }
  }
});
