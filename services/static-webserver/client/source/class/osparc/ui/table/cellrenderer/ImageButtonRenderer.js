/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2035 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.table.cellrenderer.ImageButtonRenderer", {
  extend: osparc.ui.table.cellrenderer.ButtonRenderer,

  construct: function(clickAction, iconPath, shouldShowFn = null) {
    this.base(arguments, clickAction);

    this.__imageCache = {};
    this.__shouldShowFn = shouldShowFn;

    this.setIconPath(iconPath);
  },

  properties: {
    iconPath: {
      check: "String",
      init: null,
      nullable: false,
      apply: "__applyIconPath",
    },
  },

  members: {
    __imageCache: null,
    __shouldShowFn: null,

    // overridden to play with it's visibility
    createDataCellHtml: function(cellInfo, htmlArr) {
      const shouldShow = this.__shouldShowFn
        ?
        this.__shouldShowFn(cellInfo)
        :
        true;
      if (!shouldShow) {
        return ""; // Hide button
      }
      return this.base(arguments, cellInfo, htmlArr);
    },

    __applyIconPath: function(iconPath) {
      const resMgr = qx.util.ResourceManager.getInstance();
      const iconUrl = resMgr.toUri(iconPath);

      // Create a data URI or use a more cache-friendly approach
      // Use base64 encoding for small icons (best for caching)
      this.__loadImageAsDataUri(iconUrl, iconPath);
    },

    __loadImageAsDataUri: function(iconUrl, iconPath) {
      if (this.__imageCache[iconPath]) {
        this.setButtonContent(this.__imageCache[iconPath]);
        return;
      }

      // Fetch and convert to data URI for permanent caching
      fetch(iconUrl)
        .then(response => response.blob())
        .then(blob => {
          const reader = new FileReader();
          reader.onload = () => {
            const dataUri = reader.result;
            const content = `<img src="${dataUri}" style="width:14px; height:14px;" alt="icon"/>`;

            // Cache the data URI
            this.__imageCache[iconPath] = content;
            this.setButtonContent(content);
          };
          reader.readAsDataURL(blob);
        })
        .catch(err => {
          console.warn("Failed to cache icon as data URI:", iconPath, err);
          // Fallback to original method
          this.setButtonContent(`<img src="${iconUrl}" style="width:14px; height:14px;" alt="icon"/>`);
        });
    },
  }
});
