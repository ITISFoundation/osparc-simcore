/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobi Oetiker (oetiker)

************************************************************************ */

/**
 * Collection of methods for doing MymeType operations.
 * https://en.wikipedia.org/wiki/Media_type
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const sameType = osparc.data.MimeType(mtA).match(new osparc.data.MimeType(mtB));
 * </pre>
 */

qx.Class.define("osparc.data.MimeType", {
  extend: qx.core.Object,

  properties: {
    type: {},
    subType: {},
    parameters: {}
  },

  /**
    * @param string {String} source string
  */
  construct: function(string) {
    this.base(arguments);
    this.parse(string);
  },

  statics: {
    getMimeType: function(type) {
      let match = type.match(/data:([^/\s]+\/[^/;\s]*)/);
      if (match) {
        return match[1];
      }
      return null;
    }
  },

  members: {
    parse: function(string) {
      let input = String(string).split(";");
      let essence = input.shift().split("/", 2);
      this.setType(essence[0].toLowerCase());
      this.setSubType(essence[1].toLowerCase());
      let para = {};
      input.forEach(function(p) {
        let kv = p.split("=", 2);
        para[kv[0]] = kv[1];
      });
      this.setParameters(para);
    },
    toString: function() {
      let p = this.getParameters();
      let kv = Object.keys(p)
        .sort(function(a, b) {
          a=String(a);
          b=String(b);
          if (a > b) {
            return 1;
          }
          if (a < b) {
            return -1;
          }
          return 0;
        })
        .map(function(k) {
          return k+"="+p[k];
        })
        .join(";");
      return this.getEssence() + (kv ? ";"+kv : "");
    },
    getEssence: function() {
      return this.getType() + "/" + this.getSubType();
    },
    match: function(partner) {
      let matchType = this.getType() === partner.getType() || this.getType() === "*" || partner.getType() === "*";
      let matchSubType = this.getSubType() === partner.getSubType() || this.getSubType() === "*" || partner.getSubType() === "*";
      return matchType && matchSubType;
    }
  }
});
