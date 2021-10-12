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
        study.getUi().addListener("changeMode", () => this.evalSlidesButtons());
        this.evalSlidesButtons();
        this.evalSnapshotsButtons();
      }
    },

    evalSlidesButtons: function() {
      const study = this.getStudy();
      if (study) {
        const editorContext = this.getStudy().getUi().getMode();
        const areSlidesEnabled = osparc.data.Permissions.getInstance().canDo("study.slides");
        const isOwner = osparc.data.model.Study.isOwner(study);
        this.__editSlidesButton.setEnabled(editorContext === "workbench" && areSlidesEnabled && isOwner);
        this.__startSlidesButton.setEnabled(editorContext !== "guided" && study.hasSlideshow());
        this.__startAppButton.setEnabled(editorContext !== "app" && study.getWorkbench().isPipelineLinear());
        this.__stopSlidesButton.setEnabled(["guided", "app"].includes(editorContext));
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
