/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (ignapas)

************************************************************************ */

qx.Class.define("osparc.desktop.RadioCollapsibleViews", {
  extend: qx.core.Object,

  /**
   * @param {Array} collapsibleViews array of osparc.widget.CollapsibleView
   */
  construct: function(collapsibleViews = []) {
    this.base(arguments);

    this.__collapsibleViews = [];

    collapsibleViews.forEach(cv => this.addCollapsibleView(cv));
  },

  members: {
    __collapsibleViews: null,

    /**
     * @param {osparc.widget.CollapsibleView | osparc.desktop.PanelView} collapsibleView
     */
    addCollapsibleView: function(collapsibleView) {
      this.__collapsibleViews.push(collapsibleView);

      collapsibleView.addListener("changeCollapsed", e => {
        const collapsed = e.getData();
        if (collapsed === false) {
          // close the other views
          const idx = this.__collapsibleViews.indexOf(collapsibleView);
          this.__collapsibleViews.forEach((cv, idx2) => {
            if (idx !== idx2) {
              cv.setCollapsed(true);
            }
          })
        }
      }, this);
    },

    openCollapsibleView: function(idx = 0) {
      if (idx < this.__collapsibleViews.length) {
        this.__collapsibleViews[idx].setCollapsed(false);
      }
    }
  }
});
