/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Common code for fetch buttons used in both toolbar.FetchButton and form.FetchButton
 */
qx.Mixin.define("osparc.ui.mixin.FetchButton", {
  properties: {
    fetching: {
      check: "Boolean",
      nullable: false,
      init: false,
      apply: "_applyFetching"
    }
  },
  members: {
    __icon: null,
    _applyFetching: function(isFetching, old) {
      if (isFetching) {
        this.__icon = this.getIcon();
        this.setIcon("@FontAwesome5Solid/circle-notch/12");
        this.getChildControl("icon").getContentElement().addClass("rotate");
      } else {
        if (isFetching !== old) {
          this.setIcon(this.__icon);
        }
        if (this.getChildControl("icon")) {
          this.getChildControl("icon").getContentElement().removeClass("rotate");
        }
      }
      // Might have been destroyed already
      if (this.getLayoutParent()) {
        this.setEnabled(!isFetching);
      }
    }
  }
});
