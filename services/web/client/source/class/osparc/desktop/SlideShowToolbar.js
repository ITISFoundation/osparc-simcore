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

  members: {
    __navNodes: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "edit-slideshow-buttons": {
          control = new qx.ui.container.Stack();
          const editBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/edit/14").set({
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS
          });
          const saveBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/check/14").set({
            ...osparc.navigation.NavigationBar.BUTTON_OPTIONS
          });
          editBtn.addListener("execute", () => {
            this.__navNodes.setEditMode(true);
            control.setSelection([saveBtn]);
          }, this);
          saveBtn.addListener("execute", () => {
            this.__navNodes.setEditMode(false);
            control.setSelection([editBtn]);
          }, this);
          control.add(editBtn);
          control.add(saveBtn);
          control.setSelection([editBtn]);
          this._add(control);
          break;
        }
        case "breadcrumb-navigation": {
          const breadcrumbNavigation = this.__navNodes = new osparc.navigation.BreadcrumbsSlideShow();
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
      this.getChildControl("prev-next-btns");

      this._add(new qx.ui.core.Spacer(20));

      this._startStopBtns = this.getChildControl("start-stop-btns");
    },

    // overriden
    _populateNodesNavigationLayout: function() {
      const study = this.getStudy();
      if (study) {
        const editSlideshowButtons = this.getChildControl("edit-slideshow-buttons");
        osparc.data.model.Study.isOwner(study) ? editSlideshowButtons.show() : editSlideshowButtons.exclude();

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

        this.__navNodes.populateButtons(nodeIds);
        this.getChildControl("prev-next-btns").populateButtons(nodeIds);
      }
    }
  }
});
