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

qx.Class.define("osparc.desktop.SlideshowToolbar", {
  extend: osparc.desktop.Toolbar,

  events: {
    "saveSlideshow": "qx.event.type.Event",
    "addServiceBetween": "qx.event.type.Data",
    "removeNode": "qx.event.type.Data",
    "showNode": "qx.event.type.Data",
    "hideNode": "qx.event.type.Data",
    "slidesStop": "qx.event.type.Event"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "study-info":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/info-circle/14").set({
            backgroundColor: "transparent"
          });
          control.addListener("execute", () => this.__openStudyDetails(), this);
          this._add(control);
          break;
        case "study-title":
          control = new qx.ui.basic.Label().set({
            marginLeft: 10,
            maxWidth: 200,
            font: "title-16"
          });
          this._add(control);
          break;
        case "edit-slideshow-buttons": {
          control = new qx.ui.container.Stack();
          const editBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/edit/14").set({
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
            toolTipText: this.tr("Edit Slideshow")
          });
          editBtn.editing = false;
          const saveBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/check/14").set({
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
            toolTipText: this.tr("Save Slideshow")
          });
          saveBtn.editing = true;
          editBtn.addListener("execute", () => {
            this.getChildControl("breadcrumbs-scroll").exclude();
            this.getChildControl("breadcrumbs-scroll-edit").show();
            control.setSelection([saveBtn]);
          }, this);
          saveBtn.addListener("execute", () => {
            this.getChildControl("breadcrumbs-scroll").show();
            this.getChildControl("breadcrumbs-scroll-edit").exclude();
            control.setSelection([editBtn]);
            this.fireEvent("saveSlideshow");
          }, this);
          control.add(editBtn);
          control.add(saveBtn);
          control.setSelection([editBtn]);
          this._add(control);
          break;
        }
        case "breadcrumbs-scroll":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          break;
        case "breadcrumb-navigation": {
          control = new osparc.navigation.BreadcrumbsSlideshow();
          control.addListener("nodeSelected", e => this.fireDataEvent("nodeSelected", e.getData()), this);
          const scroll = this.getChildControl("breadcrumbs-scroll");
          scroll.add(control);
          break;
        }
        case "breadcrumbs-scroll-edit":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          break;
        case "breadcrumb-navigation-edit": {
          control = new osparc.navigation.BreadcrumbsSlideshowEdit();
          [
            "addServiceBetween",
            "removeNode",
            "showNode",
            "hideNode"
          ].forEach(eventName => {
            control.addListener(eventName, e => {
              this.fireDataEvent(eventName, e.getData());
            });
          });
          const scroll = this.getChildControl("breadcrumbs-scroll-edit");
          scroll.add(control);
          break;
        }
        case "stop-slideshow":
          control = new qx.ui.form.Button().set({
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
            label: this.tr("Stop App"),
            icon: "@FontAwesome5Solid/stop/14"
          });
          control.addListener("execute", () => this.fireEvent("slidesStop"));
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    // overridden
    _buildLayout: function() {
      this.getChildControl("study-info");
      this.getChildControl("study-title");

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this.getChildControl("edit-slideshow-buttons");
      this.getChildControl("breadcrumb-navigation");
      this.getChildControl("breadcrumb-navigation-edit");

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this.getChildControl("stop-slideshow");
    },

    // overridden
    _applyStudy: function(study) {
      this.base(arguments, study);

      if (study) {
        const studyTitle = this.getChildControl("study-title");
        study.bind("name", studyTitle, "value");
        study.bind("name", studyTitle, "toolTipText");
      }
    },

    // overridden
    _populateNodesNavigationLayout: function() {
      const study = this.getStudy();
      if (study) {
        const editSlideshowButtons = this.getChildControl("edit-slideshow-buttons");
        osparc.data.model.Study.isOwner(study) ? editSlideshowButtons.show() : editSlideshowButtons.exclude();
        if (!study.getWorkbench().isPipelineLinear()) {
          editSlideshowButtons.exclude();
        }

        const nodeIds = study.getUi().getSlideshow().getSortedNodeIds();
        this.getChildControl("breadcrumb-navigation").populateButtons(nodeIds);
        this.getChildControl("breadcrumb-navigation-edit").populateButtons(study);
        this.__evalButtonsIfEditing();
      }
    },

    populateButtons: function(start = false) {
      this._populateNodesNavigationLayout();
      if (start) {
        const editSlideshowButtons = this.getChildControl("edit-slideshow-buttons");
        const currentModeBtn = editSlideshowButtons.getSelection()[0];
        if ("editing" in currentModeBtn && currentModeBtn["editing"]) {
          currentModeBtn.execute();
        }
      }
    },

    __openStudyDetails: function() {
      const studyDetails = new osparc.studycard.Large(this.getStudy());
      const title = this.tr("Study Details");
      const width = 500;
      const height = 500;
      osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height);
    },

    __evalButtonsIfEditing: function() {
      const editSlideshowButtons = this.getChildControl("edit-slideshow-buttons");
      const currentModeBtn = editSlideshowButtons.getSelection()[0];
      if ("editing" in currentModeBtn && currentModeBtn["editing"]) {
        this.getChildControl("breadcrumbs-scroll").exclude();
        this.getChildControl("breadcrumbs-scroll-edit").show();
      } else {
        this.getChildControl("breadcrumbs-scroll").show();
        this.getChildControl("breadcrumbs-scroll-edit").exclude();
      }
    }
  }
});
