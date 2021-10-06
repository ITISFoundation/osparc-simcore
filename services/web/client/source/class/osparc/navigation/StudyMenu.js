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

qx.Class.define("osparc.navigation.StudyMenu", {
  extend: qx.ui.form.MenuButton,

  construct: function() {
    this.base(arguments, this.tr("Study options"));

    this.set({
      ...osparc.navigation.NavigationBar.BUTTON_OPTIONS
    });

    this.__populateMenu();
  },

  events: {
    "infoButtonPressed": "qx.event.type.Event",
    "slidesGuidedStart": "qx.event.type.Event",
    "slidesAppStart": "qx.event.type.Event",
    "slidesStop": "qx.event.type.Event",
    "slidesEdit": "qx.event.type.Event",
    "takeSnapshot": "qx.event.type.Event",
    "showSnapshots": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: true,
      apply: "_applyStudy"
    }
  },

  members: {
    __startSlidesButton: null,
    __startAppButton: null,
    __editSlidesButton: null,
    __stopSlidesButton: null,
    __takeSnapshotButton: null,
    __showSnapshotsButton: null,

    __populateMenu: function() {
      const studyButtonMenu = new qx.ui.menu.Menu();
      this.setMenu(studyButtonMenu);

      const studyInfoButton = new qx.ui.menu.Button(this.tr("More Information"));
      studyInfoButton.addListener("execute", () => this.fireEvent("infoButtonPressed"), this);
      studyButtonMenu.add(studyInfoButton);

      studyButtonMenu.addSeparator();

      const editSlidesBtn = this.__editSlidesButton = new qx.ui.menu.Button(this.tr("Edit Slideshow"));
      editSlidesBtn.addListener("execute", () => this.fireEvent("slidesEdit"), this);
      studyButtonMenu.add(editSlidesBtn);

      const startGuidedBtn = this.__startSlidesButton = new qx.ui.menu.Button(this.tr("Start Guided Mode"));
      startGuidedBtn.addListener("execute", () => this.fireEvent("slidesGuidedStart"), this);
      studyButtonMenu.add(startGuidedBtn);

      const startAppBtn = this.__startAppButton = new qx.ui.menu.Button(this.tr("Start App Mode"));
      startAppBtn.addListener("execute", () => this.fireEvent("slidesAppStart"), this);
      studyButtonMenu.add(startAppBtn);

      const stopSlidesBtn = this.__stopSlidesButton = new qx.ui.menu.Button(this.tr("Stop Slideshow"));
      stopSlidesBtn.addListener("execute", () => this.fireEvent("slidesStop"), this);
      studyButtonMenu.add(stopSlidesBtn);

      studyButtonMenu.addSeparator();

      const takeSnapshotBtn = this.__takeSnapshotButton = new qx.ui.menu.Button(this.tr("Take Snapshot"));
      takeSnapshotBtn.addListener("execute", () => this.fireEvent("takeSnapshot"), this);
      studyButtonMenu.add(takeSnapshotBtn);

      const showSnapshotsBtn = this.__showSnapshotsButton = new qx.ui.menu.Button(this.tr("Show Snapshots"));
      showSnapshotsBtn.addListener("execute", () => this.fireEvent("showSnapshots"), this);
      studyButtonMenu.add(showSnapshotsBtn);
    },

    _applyStudy: function(study) {
      if (study) {
        study.getWorkbench().addListener("pipelineChanged", () => this.evalSlidesButtons());
        study.getUi().getSlideshow().addListener("changeSlideshow", () => this.evalSlidesButtons());
        this.evalSlidesButtons();

        study.getWorkbench().addListener("nNodesChanged", this.evalSnapshotsButtons());
        this.evalSnapshotsButtons();
      }
    },

    evalSlidesButtons: function(editorContext) {
      console.log("evalSlidesButtons", editorContext);
      const slidesBtnsVisible = ["workbench", "guided", "app"].includes(editorContext);
      if (slidesBtnsVisible) {
        const study = this.getStudy();
        const areSlidesEnabled = osparc.data.Permissions.getInstance().canDo("study.slides");
        if (areSlidesEnabled) {
          this.__startSlidesButton.setEnabled(study.hasSlideshow());
          this.__startAppButton.setEnabled(study.getWorkbench().isPipelineLinear());
          const isOwner = osparc.data.model.Study.isOwner(study);
          this.__editSlidesButton.setEnabled(areSlidesEnabled && isOwner);

          if (["guided", "app"].includes(editorContext)) {
            this.__stopSlidesButton.setEnabled(true);
          } else if (editorContext === "workbench") {
            this.__stopSlidesButton.setEnabled(false);
          }
        }
      } else {
        this.__stopSlidesButton.setEnabled(false);
      }
    },

    evalSnapshotsButtons: async function() {
      const study = this.getStudy();
      if (study) {
        this.__takeSnapshotButton.setEnabled(osparc.data.Permissions.getInstance().canDo("study.snapshot.create"));

        const hasSnapshots = await study.hasSnapshots();
        this.__showSnapshotsButton.setEnabled(hasSnapshots);
      }
    }
  }
});
