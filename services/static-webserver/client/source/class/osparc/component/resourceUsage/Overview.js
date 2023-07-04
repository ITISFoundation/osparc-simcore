/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.resourceUsage.Overview", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__fetchData();
  },

  statics: {
    ITEMS_PER_PAGE: 10,

    popUpInWindow: function() {
      const title = qx.locale.Manager.tr("Usage Overview");
      const noteEditor = new osparc.component.resourceUsage.Overview();
      const win = osparc.ui.window.Window.popUpInWindow(noteEditor, title, 325, 256);
      win.center();
      win.open();
      return win;
    }
  },

  members: {
    __nextRequestParams: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/paw/14",
            alignX: "center",
            alignY: "middle",
            minWidth: 18
          });
          this._add(control, {
            row: 0,
            column: 0,
            rowSpan: 3
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __fetchData: function() {

    },


    fetchComments: function(removeComments = true) {
      const loadMoreButton = this.getChildControl("load-more-button");
      loadMoreButton.show();
      loadMoreButton.setFetching(true);

      if (removeComments) {
        this.getChildControl("comments-list").removeAll();
      }

      this.__getNextRequest()
        .then(resp => {
          const comments = resp["data"];
          this.__addComments(comments);
          this.__nextRequestParams = resp["_links"]["next"];
          if (this.__nextRequestParams === null) {
            loadMoreButton.exclude();
          }
        })
        .finally(() => loadMoreButton.setFetching(false));
    },

    __getNextRequest: function() {
      const params = {
        url: {
          offset: 0,
          limit: osparc.component.resourceUsage.Overview.ITEMS_PER_PAGE
        }
      };
      const nextRequestParams = this.__nextRequestParams;
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("resourceUsage", "getPage", params, undefined, options);
    }
  }
});
