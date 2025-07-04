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

  construct: function(clickAction, iconPath) {
    this.base(arguments, clickAction);

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
    __applyIconPath: function(iconPath) {
      const resMgr = qx.util.ResourceManager.getInstance();
      const iconUrl = resMgr.toUri(iconPath);

      // Create a data URI or use a more cache-friendly approach
      // Use base64 encoding for small icons (best for caching)
      this.__loadImageAsDataUri(iconUrl, iconPath);
    },

    __loadImageAsDataUri: function(iconUrl, iconPath) {
      // Try to use a cached version first
      if (this.constructor.__imageCache && this.constructor.__imageCache[iconPath]) {
        this.setButtonContent(this.constructor.__imageCache[iconPath]);
        return;
      }

      // Initialize cache if it doesn't exist
      if (!this.constructor.__imageCache) {
        this.constructor.__imageCache = {};
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
            this.constructor.__imageCache[iconPath] = content;
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
