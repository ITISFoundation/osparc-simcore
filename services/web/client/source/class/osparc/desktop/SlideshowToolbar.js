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
        case "prev-next-btns": {
          control = new osparc.navigation.PrevNextButtons();
          control.addListener("nodeSelected", e => {
            this.fireDataEvent("nodeSelected", e.getData());
          }, this);
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
          control.addListener("nodeSelected", e => {
            this.fireDataEvent("nodeSelected", e.getData());
          }, this);
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
            label: this.tr("Stop Slideshow"),
            icon: "@FontAwesome5Solid/stop/14"
          });
          control.addListener("execute", () => this.fireEvent("slidesStop"));
          break;
      }
      return control || this.base(arguments, id);
    },

    // overriden
    _buildLayout: function() {
      this.getChildControl("edit-slideshow-buttons");
      this.getChildControl("prev-next-btns");
      this.getChildControl("breadcrumb-navigation");
      this.getChildControl("breadcrumb-navigation-edit");

      this._add(new qx.ui.core.Spacer(20));

      this.getChildControl("stop-slideshow");

      this._add(new qx.ui.core.Spacer(20));

      this._startStopBtns = this.getChildControl("start-stop-btns");
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

    // overriden
    _populateNodesNavigationLayout: function() {
      const study = this.getStudy();
      if (study) {
        const editSlideshowButtons = this.getChildControl("edit-slideshow-buttons");
        osparc.data.model.Study.isOwner(study) ? editSlideshowButtons.show() : editSlideshowButtons.exclude();
        if (!study.getWorkbench().isPipelineLinear()) {
          editSlideshowButtons.exclude();
        }

        const nodes = study.getUi().getSlideshow().getSortedNodes();
        const nodeIds = [];
        nodes.forEach(node => {
          nodeIds.push(node.nodeId);
        });

        this.getChildControl("breadcrumb-navigation").populateButtons(nodeIds);
        this.getChildControl("breadcrumb-navigation-edit").populateButtons(study);
        const currentModeBtn = editSlideshowButtons.getSelection()[0];
        if ("editing" in currentModeBtn && currentModeBtn["editing"]) {
          this.getChildControl("prev-next-btns").exclude();
          this.getChildControl("breadcrumbs-scroll").exclude();
          this.getChildControl("breadcrumbs-scroll-edit").show();
          this.getChildControl("start-stop-btns").exclude();
        } else {
          this.getChildControl("prev-next-btns").show();
          this.getChildControl("breadcrumbs-scroll").show();
          this.getChildControl("breadcrumbs-scroll-edit").exclude();
          this.getChildControl("start-stop-btns").show();
        }

        this.getChildControl("prev-next-btns").populateButtons(nodeIds);
      }
    }
  }
});
