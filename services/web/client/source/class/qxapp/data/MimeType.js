// https://en.wikipedia.org/wiki/Media_type
qx.Class.define("qxapp.data.MimeType", {
  extend: qx.core.Object,

  properties: {
    type: {},
    subType: {},
    parameters: {}
  },

  construct: function(string) {
    this.base(arguments);
    this.parse(string);
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
      let matchSubType = this.getSubType() === partner.getSubType() || this.getSubStype() === "*" || partner.getSubType() === "*";
      return matchType && matchSubType;
    }
  }
});
