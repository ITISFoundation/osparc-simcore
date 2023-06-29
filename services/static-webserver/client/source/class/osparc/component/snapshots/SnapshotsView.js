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

/**
 * @ignore(fetch)
 */

qx.Class.define("osparc.component.snapshots.SnapshotsView", {
  extend: qx.ui.splitpane.Pane,

  construct: function(study) {
    this.base(arguments, "horizontal");

    this.__study = study;
    this.__buildLayout();
  },

  events: {
    "updateSnapshot": "qx.event.type.Data",
    "openSnapshot": "qx.event.type.Data"
  },

  members: {
    __snapshotsSection: null,
    __gitGraphScrollLayout: null,
    __gitGraphWrapper: null,
    __snapshotPreview: null,
    __editSnapshotBtn: null,
    __openSnapshotBtn: null,
    __snapshots: null,
    __currentSnapshot: null,
    __selectedSnapshotId: null,

    __buildLayout: function() {
      const snapshotsSection = this.__snapshotsSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      this.add(snapshotsSection, 1);

      this.__rebuildSnapshots();
      this.__buildSnapshotButtons();

      const snapshotPreview = this.__snapshotPreview = new osparc.component.workbench.WorkbenchUIPreview();
      this.add(snapshotPreview, 1);
    },

    __rebuildSnapshots: function() {
      Promise.all([
        this.__study.getSnapshots(),
        this.__study.getCurrentSnapshot()
      ])
        .then(values => {
          this.__snapshots = values[0];
          this.__currentSnapshot = values[1];
          this.__rebuildSnapshotsGraph();
        });
    },

    __rebuildSnapshotsGraph: function() {
      if (this.__gitGraphScrollLayout) {
        this.__snapshotsSection.remove(this.__gitGraphScrollLayout);
      }

      const gitGraphLayout = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      const gitGraphCanvas = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      const gitGraphInteract = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      gitGraphLayout.add(gitGraphCanvas, {
        top: 20,
        right: 0,
        bottom: 0,
        left: 0
      });
      gitGraphLayout.add(gitGraphInteract, {
        top: 20 + 2,
        right: 0,
        bottom: 0,
        left: 0
      });

      gitGraphCanvas.addListenerOnce("appear", () => {
        const gitGraphWrapper = this.__gitGraphWrapper = new osparc.wrapper.GitGraph();
        gitGraphWrapper.init(gitGraphCanvas, gitGraphInteract)
          .then(() => {
            gitGraphWrapper.populateGraph(this.__snapshots, this.__currentSnapshot);
            this.__snapshotSelected(this.__currentSnapshot["id"]);
          });
        gitGraphWrapper.addListener("snapshotTap", e => {
          const snapshotId = e.getData();
          this.__snapshotSelected(snapshotId);
        });
      });

      const scroll = this.__gitGraphScrollLayout = new qx.ui.container.Scroll();
      scroll.add(gitGraphLayout);
      this._add(scroll, {
        flex: 1
      });

      this.__snapshotsSection.addAt(scroll, 0, {
        flex: 1
      });
    },

    __buildSnapshotButtons: function() {
      const buttonsSection = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      this._add(buttonsSection);

      const editSnapshotBtn = this.__editSnapshotBtn = this.__createEditSnapshotBtn();
      editSnapshotBtn.setEnabled(false);
      editSnapshotBtn.addListener("execute", () => {
        if (this.__selectedSnapshotId) {
          this.__editSnapshot(this.__selectedSnapshotId);
        }
      });
      buttonsSection.add(editSnapshotBtn);

      const openSnapshotBtn = this.__openSnapshotBtn = this.__createOpenSnapshotBtn();
      openSnapshotBtn.setEnabled(false);
      openSnapshotBtn.addListener("execute", () => {
        if (this.__selectedSnapshotId) {
          this.fireDataEvent("openSnapshot", this.__selectedSnapshotId);
        }
      });
      buttonsSection.add(openSnapshotBtn);

      this.__snapshotsSection.addAt(buttonsSection, 1);
    },

    __createEditSnapshotBtn: function() {
      const editSnapshotBtn = new qx.ui.form.Button(this.tr("Edit Tag")).set({
        allowGrowX: false,
        alignX: "left"
      });
      return editSnapshotBtn;
    },

    __createOpenSnapshotBtn: function() {
      const openSnapshotBtn = new qx.ui.form.Button(this.tr("Open")).set({
        allowGrowX: false,
        alignX: "right"
      });
      return openSnapshotBtn;
    },

    __editSnapshot: function(snapshotId) {
      const selectedSnapshot = this.__snapshots.find(snapshot => snapshot["id"] === snapshotId);
      if (selectedSnapshot) {
        const editSnapshotView = new osparc.component.snapshots.EditSnapshotView();
        const tagCtrl = editSnapshotView.getChildControl("tags");
        tagCtrl.setValue(selectedSnapshot["tags"][0]);
        const msgCtrl = editSnapshotView.getChildControl("message");
        msgCtrl.setValue(selectedSnapshot["message"]);
        const title = this.tr("Edit Snapshot");
        const win = osparc.ui.window.Window.popUpInWindow(editSnapshotView, title, 400, 180);
        editSnapshotView.addListener("takeSnapshot", () => {
          const params = {
            url: {
              "studyId": this.__study.getUuid(),
              "snapshotId": snapshotId
            },
            data: {
              "tag": editSnapshotView.getTag(),
              "message": editSnapshotView.getMessage()
            }
          };
          osparc.data.Resources.fetch("snapshots", "updateSnapshot", params)
            .then(() => {
              this.__rebuildSnapshots();
            })
            .catch(err => osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR"));
          win.close();
        }, this);
        editSnapshotView.addListener("cancel", () => {
          win.close();
        }, this);
      }
    },

    __snapshotSelected: function(snapshotId) {
      this.__selectedSnapshotId = snapshotId;

      if (this.__gitGraphWrapper) {
        this.__gitGraphWrapper.setSelection(snapshotId);
      }

      this.__loadSnapshotsPreview(snapshotId);

      if (this.__editSnapshotBtn) {
        this.__editSnapshotBtn.setEnabled(true);
      }

      if (this.__openSnapshotBtn) {
        this.__openSnapshotBtn.setEnabled(true);
      }
    },

    __loadSnapshotsPreview: function(snapshotId) {
      const params = {
        url: {
          "studyId": this.__study.getUuid(),
          "snapshotId": snapshotId
        }
      };
      osparc.data.Resources.fetch("snapshots", "preview", params)
        .then(data => {
          const studyData = this.__study.serialize();
          studyData["workbench"] = data["workbench"];
          studyData["ui"] = data["ui"];
          const study = new osparc.data.model.Study(studyData);
          study.setReadOnly(true);
          this.__snapshotPreview.set({
            study: study
          });
          this.__snapshotPreview.loadModel(study.getWorkbench());
        });
    }
  }
});
