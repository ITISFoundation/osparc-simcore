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
  extend: osparc.desktop.Toolbar,

  events: {
    "addServiceBetween": "qx.event.type.Data",
    "removeNode": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "edit-slideshow-buttons": {
          control = new qx.ui.container.Stack();
          const editBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/edit/14").set({
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS
          });
          editBtn.editing = false;
          const saveBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/check/14").set({
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS
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
          control = new osparc.navigation.BreadcrumbsSlideShow();
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
          control = new osparc.navigation.BreadcrumbsSlideShowEdit();
          control.addListener("addServiceBetween", e => {
            this.fireDataEvent("addServiceBetween", e.getData());
          }, this);
          control.addListener("removeNode", e => {
            this.fireDataEvent("removeNode", e.getData());
          }, this);
          const scroll = this.getChildControl("breadcrumbs-scroll-edit");
          scroll.add(control);
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
      }
      return control || this.base(arguments, id);
    },

    // overriden
    _buildLayout: function() {
      this.getChildControl("edit-slideshow-buttons");
      this.getChildControl("breadcrumb-navigation");
      this.getChildControl("breadcrumb-navigation-edit");
      this.getChildControl("prev-next-btns");

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
        this.getChildControl("breadcrumb-navigation-edit").populateButtons(nodeIds);
        this.getChildControl("prev-next-btns").populateButtons(nodeIds);

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
  }
});
