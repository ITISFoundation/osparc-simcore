//
// Autogenerated by Thrift Compiler (0.11.0)
//
// DO NOT EDIT UNLESS YOU ARE SURE THAT YOU KNOW WHAT YOU ARE DOING
//
"use strict";

var thrift = require('thrift');
var Thrift = thrift.Thrift;
var Q = thrift.Q;


var SharedService = require('./SharedService');
var SharedServiceClient = SharedService.Client;
var SharedServiceProcessor = SharedService.Processor;
var ttypes = require('./application_types');
//HELPER FUNCTIONS AND STRUCTURES

var Logger_GetNextRecord_args = function(args) {
};
Logger_GetNextRecord_args.prototype = {};
Logger_GetNextRecord_args.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    input.skip(ftype);
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

Logger_GetNextRecord_args.prototype.write = function(output) {
  output.writeStructBegin('Logger_GetNextRecord_args');
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var Logger_GetNextRecord_result = function(args) {
  this.success = null;
  if (args) {
    if (args.success !== undefined && args.success !== null) {
      this.success = Thrift.copyMap(args.success, [null]);
    }
  }
};
Logger_GetNextRecord_result.prototype = {};
Logger_GetNextRecord_result.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 0:
      if (ftype == Thrift.Type.MAP) {
        var _size34 = 0;
        var _rtmp338;
        this.success = {};
        var _ktype35 = 0;
        var _vtype36 = 0;
        _rtmp338 = input.readMapBegin();
        _ktype35 = _rtmp338.ktype;
        _vtype36 = _rtmp338.vtype;
        _size34 = _rtmp338.size;
        for (var _i39 = 0; _i39 < _size34; ++_i39)
        {
          var key40 = null;
          var val41 = null;
          key40 = input.readString();
          val41 = input.readString();
          this.success[key40] = val41;
        }
        input.readMapEnd();
      } else {
        input.skip(ftype);
      }
      break;
      case 0:
        input.skip(ftype);
        break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

Logger_GetNextRecord_result.prototype.write = function(output) {
  output.writeStructBegin('Logger_GetNextRecord_result');
  if (this.success !== null && this.success !== undefined) {
    output.writeFieldBegin('success', Thrift.Type.MAP, 0);
    output.writeMapBegin(Thrift.Type.STRING, Thrift.Type.STRING, Thrift.objectLength(this.success));
    for (var kiter42 in this.success)
    {
      if (this.success.hasOwnProperty(kiter42))
      {
        var viter43 = this.success[kiter42];
        output.writeString(kiter42);
        output.writeString(viter43);
      }
    }
    output.writeMapEnd();
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var Logger_SetRecordLogLevel_args = function(args) {
  this.min_log_level = null;
  if (args) {
    if (args.min_log_level !== undefined && args.min_log_level !== null) {
      this.min_log_level = args.min_log_level;
    }
  }
};
Logger_SetRecordLogLevel_args.prototype = {};
Logger_SetRecordLogLevel_args.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 1:
      if (ftype == Thrift.Type.I64) {
        this.min_log_level = input.readI64();
      } else {
        input.skip(ftype);
      }
      break;
      case 0:
        input.skip(ftype);
        break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

Logger_SetRecordLogLevel_args.prototype.write = function(output) {
  output.writeStructBegin('Logger_SetRecordLogLevel_args');
  if (this.min_log_level !== null && this.min_log_level !== undefined) {
    output.writeFieldBegin('min_log_level', Thrift.Type.I64, 1);
    output.writeI64(this.min_log_level);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var Logger_SetRecordLogLevel_result = function(args) {
};
Logger_SetRecordLogLevel_result.prototype = {};
Logger_SetRecordLogLevel_result.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    input.skip(ftype);
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

Logger_SetRecordLogLevel_result.prototype.write = function(output) {
  output.writeStructBegin('Logger_SetRecordLogLevel_result');
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var LoggerClient = exports.Client = function(output, pClass) {
    this.output = output;
    this.pClass = pClass;
    this._seqid = 0;
    this._reqs = {};
};
Thrift.inherits(LoggerClient, SharedServiceClient);
LoggerClient.prototype.seqid = function() { return this._seqid; };
LoggerClient.prototype.new_seqid = function() { return this._seqid += 1; };
LoggerClient.prototype.GetNextRecord = function(callback) {
  this._seqid = this.new_seqid();
  if (callback === undefined) {
    var _defer = Q.defer();
    this._reqs[this.seqid()] = function(error, result) {
      if (error) {
        _defer.reject(error);
      } else {
        _defer.resolve(result);
      }
    };
    this.send_GetNextRecord();
    return _defer.promise;
  } else {
    this._reqs[this.seqid()] = callback;
    this.send_GetNextRecord();
  }
};

LoggerClient.prototype.send_GetNextRecord = function() {
  var output = new this.pClass(this.output);
  output.writeMessageBegin('GetNextRecord', Thrift.MessageType.CALL, this.seqid());
  var args = new Logger_GetNextRecord_args();
  args.write(output);
  output.writeMessageEnd();
  return this.output.flush();
};

LoggerClient.prototype.recv_GetNextRecord = function(input,mtype,rseqid) {
  var callback = this._reqs[rseqid] || function() {};
  delete this._reqs[rseqid];
  if (mtype == Thrift.MessageType.EXCEPTION) {
    var x = new Thrift.TApplicationException();
    x.read(input);
    input.readMessageEnd();
    return callback(x);
  }
  var result = new Logger_GetNextRecord_result();
  result.read(input);
  input.readMessageEnd();

  if (null !== result.success) {
    return callback(null, result.success);
  }
  return callback('GetNextRecord failed: unknown result');
};
LoggerClient.prototype.SetRecordLogLevel = function(min_log_level, callback) {
  this._seqid = this.new_seqid();
  if (callback === undefined) {
    var _defer = Q.defer();
    this._reqs[this.seqid()] = function(error, result) {
      if (error) {
        _defer.reject(error);
      } else {
        _defer.resolve(result);
      }
    };
    this.send_SetRecordLogLevel(min_log_level);
    return _defer.promise;
  } else {
    this._reqs[this.seqid()] = callback;
    this.send_SetRecordLogLevel(min_log_level);
  }
};

LoggerClient.prototype.send_SetRecordLogLevel = function(min_log_level) {
  var output = new this.pClass(this.output);
  output.writeMessageBegin('SetRecordLogLevel', Thrift.MessageType.ONEWAY, this.seqid());
  var params = {
    min_log_level: min_log_level
  };
  var args = new Logger_SetRecordLogLevel_args(params);
  args.write(output);
  output.writeMessageEnd();
  return this.output.flush();
};
var LoggerProcessor = exports.Processor = function(handler) {
  this._handler = handler;
}
;
Thrift.inherits(LoggerProcessor, SharedServiceProcessor);
LoggerProcessor.prototype.process = function(input, output) {
  var r = input.readMessageBegin();
  if (this['process_' + r.fname]) {
    return this['process_' + r.fname].call(this, r.rseqid, input, output);
  } else {
    input.skip(Thrift.Type.STRUCT);
    input.readMessageEnd();
    var x = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN_METHOD, 'Unknown function ' + r.fname);
    output.writeMessageBegin(r.fname, Thrift.MessageType.EXCEPTION, r.rseqid);
    x.write(output);
    output.writeMessageEnd();
    output.flush();
  }
}
;
LoggerProcessor.prototype.process_GetNextRecord = function(seqid, input, output) {
  var args = new Logger_GetNextRecord_args();
  args.read(input);
  input.readMessageEnd();
  if (this._handler.GetNextRecord.length === 0) {
    Q.fcall(this._handler.GetNextRecord.bind(this._handler))
      .then(function(result) {
        var result_obj = new Logger_GetNextRecord_result({success: result});
        output.writeMessageBegin("GetNextRecord", Thrift.MessageType.REPLY, seqid);
        result_obj.write(output);
        output.writeMessageEnd();
        output.flush();
      }, function (err) {
        var result;
        result = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("GetNextRecord", Thrift.MessageType.EXCEPTION, seqid);
        result.write(output);
        output.writeMessageEnd();
        output.flush();
      });
  } else {
    this._handler.GetNextRecord(function (err, result) {
      var result_obj;
      if ((err === null || typeof err === 'undefined')) {
        result_obj = new Logger_GetNextRecord_result((err !== null || typeof err === 'undefined') ? err : {success: result});
        output.writeMessageBegin("GetNextRecord", Thrift.MessageType.REPLY, seqid);
      } else {
        result_obj = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("GetNextRecord", Thrift.MessageType.EXCEPTION, seqid);
      }
      result_obj.write(output);
      output.writeMessageEnd();
      output.flush();
    });
  }
};
LoggerProcessor.prototype.process_SetRecordLogLevel = function(seqid, input, output) {
  var args = new Logger_SetRecordLogLevel_args();
  args.read(input);
  input.readMessageEnd();
  this._handler.SetRecordLogLevel(args.min_log_level);
}
;
