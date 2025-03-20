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

qx.Class.define("osparc.ui.table.cellrenderer.SVGButtonRenderer", {
  extend: osparc.ui.table.cellrenderer.Html,

  construct: function(id, icon) {
    this.base(arguments);
  },

  properties: {
    clickAction: {
      check: "String",
      nullable: false,
      init: "clickAction",
    },

    svgIcon: {
      check: "String",
      nullable: false,
      init: "osparc/offline.svg", // Default icon
    },
  },

  members: {
    // Override
    _getContentHtml: function(cellInfo) {
      const clickAction = this.getClickAction();
      const iconPath = this.getSvgIcon();
      const resMgr = qx.util.ResourceManager.getInstance();
      const iconUrl = resMgr.toUri(iconPath); // Resolves to the correct URL of the asset

      // Button styling
      const buttonStyle = "background:none; border:none; padding:0; cursor:pointer; height:32px; width:32px; display:flex; align-items:center; justify-content:center;";
      const imgStyle = "height:24px; width:24px;"; // Ensuring it fits nicely

      // Return the button with the image
      return `
        <button style="${buttonStyle}" data-action="${clickAction}" data-row="${cellInfo.row}" title="View">
          <img src="${iconUrl}" style="${imgStyle}" alt="icon" />
        </button>
      `;
    },

    /*
    // Helper method to get the correct FontAwesome icon as inline SVG
    _getFontAwesomeSvg: function(iconClass) {
      const iconMap = {
        "fa-cog": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="24" height="24"><path d="M487.8 317.6l-53.7-31.1c7.3-17.7 11.6-36.9 11.6-56.5 0-19.7-4.3-38.8-11.6-56.5l53.7-31.1c10.7-6.1 13.5-19.8 7.4-30.4l-41.5-71.6c-6.1-10.7-19.8-13.5-30.4-7.4l-53.7 31.1c-17.7-13.1-37.1-23.6-58.4-30.5l-8.5-55.2c-2.2-14.2-15.4-24.3-29.8-24.3h-57.8c-14.4 0-27.6 10.1-29.8 24.3l-8.5 55.2c-21.3 6.9-40.7 17.4-58.4 30.5l-53.7-31.1c-10.7-6.1-24.3-3.3-30.4 7.4l-41.5 71.6c-6.1 10.7-3.3 24.3 7.4 30.4l53.7 31.1c-7.3 17.7-11.6 36.9-11.6 56.5 0 19.7 4.3 38.8 11.6 56.5l-53.7 31.1c-10.7 6.1-13.5 19.8-7.4 30.4l41.5 71.6c6.1 10.7 19.8 13.5 30.4 7.4l53.7-31.1c17.7 13.1 37.1 23.6 58.4 30.5l8.5 55.2c2.2 14.2 15.4 24.3 29.8 24.3h57.8c14.4 0 27.6-10.1 29.8-24.3l8.5-55.2c21.3-6.9 40.7-17.4 58.4-30.5l53.7 31.1c10.7 6.1 24.3 3.3 30.4-7.4l41.5-71.6c6.1-10.7 3.3-24.3-7.4-30.4z"/></svg>',
        // Add more icons as needed...
      };

      return iconMap[iconClass] || iconMap["fa-cog"]; // Default to "fa-cog" if iconClass is not found
    }
    */
  }
});
