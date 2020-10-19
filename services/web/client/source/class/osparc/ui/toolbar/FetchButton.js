/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * A toolbar button that serves to fetch or load some data from the server. To indicate that some processing is being done, and
 * that the user has to wait, a rotating special icon is shown meanwhile.
 */
qx.Class.define("osparc.ui.toolbar.FetchButton", {
  extend: qx.ui.toolbar.Button,
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
    _applyFetching: function(isFetching) {
      if (isFetching) {
        this.__icon = this.getIcon();
        this.setIcon("@FontAwesome5Solid/circle-notch/12");
        this.getChildControl("icon").getContentElement().addClass("rotate");
      } else {
        if (this.__icon !== null) {
          this.setIcon(this.__icon);
        }
        this.getChildControl("icon").getContentElement().removeClass("rotate");
      }
      this.setEnabled(!isFetching);
    }
  }
});
