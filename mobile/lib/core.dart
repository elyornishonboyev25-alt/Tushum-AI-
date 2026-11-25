import 'dart:async';
import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';

typedef Json = Map<String, dynamic>;
const uuid = Uuid();

int integer(dynamic value) => (value as num?)?.toInt() ?? 0;
String text(dynamic value) => value?.toString() ?? '';

String formatMoney(dynamic cents, {bool unit = true}) {
  final value = integer(cents);
  final formatted = NumberFormat(
    '#,##0.##',
    'en_US',
  ).format(value / 100).replaceAll(',', ' ');
  return unit ? '$formatted so‘m' : formatted;
}

String inputMoney(dynamic cents) {
  final value = integer(cents);
  return value % 100 == 0
      ? (value ~/ 100).toString()
      : (value / 100).toStringAsFixed(2);
}

String displayDate(dynamic value) {
  final parsed = DateTime.tryParse(text(value));
  if (parsed == null) return '—';
  const months = [
    'yan',
    'fev',
    'mar',
    'apr',
    'may',
    'iyn',
    'iyl',
    'avg',
    'sen',
    'okt',
    'noy',
    'dek',
  ];
  return '${parsed.day}-${months[parsed.month - 1]} ${parsed.year}';
}

String initials(String name) {
  final parts = name
      .trim()
      .split(RegExp(r'\s+'))
      .where((part) => part.isNotEmpty)
      .take(2);
  return parts.map((part) => part.characters.first.toUpperCase()).join();
}

class ApiError implements Exception {
  const ApiError(this.message, [this.status = 0]);
  final String message;
  final int status;
  @override
  String toString() => message;
}

class ApiClient {
  ApiClient(this.baseUrl);
  String baseUrl;
  String? token;
  final http.Client _client = http.Client();

  Uri uri(String path) => Uri.parse('$baseUrl$path');
  Map<String, String> get headers => {
    if (token != null) 'Authorization': 'Bearer $token',
  };

  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Json? body,
    String? operationId,
  }) async {
    try {
      final request = http.Request(method, uri(path));
      request.headers.addAll(headers);
      if (body != null) {
        request.headers['Content-Type'] = 'application/json';
        request.body = jsonEncode(body);
      }
      if (operationId != null) request.headers['X-Operation-Id'] = operationId;
      final stream = await _client
          .send(request)
          .timeout(const Duration(seconds: 25));
      final response = await http.Response.fromStream(stream)
          .timeout(const Duration(seconds: 25));
      return decode(response);
    } on ApiError {
      rethrow;
    } on TimeoutException {
      throw const ApiError(
        'Server javobi kutilmoqda. Ulanishni tekshirib, qayta urinib ko‘ring.',
      );
    } catch (_) {
      throw const ApiError(
        'Serverga ulanib bo‘lmadi. Internet va server manzilini tekshiring.',
      );
    }
  }

  dynamic decode(http.Response response) {
    dynamic value;
    try {
      value = jsonDecode(utf8.decode(response.bodyBytes));
    } catch (_) {
      throw ApiError(
        'Server javobi ochilmadi. Server manzilini tekshiring.',
        response.statusCode,
      );
    }
    if (response.statusCode >= 400) {
      throw ApiError(
        value is Map ? text(value['detail']) : 'So‘rov bajarilmadi.',
        response.statusCode,
      );
    }
    return value;
  }

  Future<Json> upload(PlatformFile file, {Json? mapping}) async {
    try {
      final bytes = await file.readAsBytes().timeout(
        const Duration(seconds: 30),
      );
      if (bytes.length > 10 * 1024 * 1024) {
        throw const ApiError('Fayl hajmi 10 MB dan oshmasin.');
      }
      final request = http.MultipartRequest(
        'POST',
        uri('/api/imports/preview'),
      );
      request.headers.addAll(headers);
      request.fields['mapping'] = jsonEncode(mapping ?? {});
      request.files.add(
        http.MultipartFile.fromBytes('file', bytes, filename: file.name),
      );
      final response = await http.Response.fromStream(
        await _client.send(request).timeout(const Duration(seconds: 60)),
      );
      return Map<String, dynamic>.from(decode(response) as Map);
    } on ApiError {
      rethrow;
    } catch (_) {
      throw const ApiError(
        'Fayl yuklanmadi. Ulanishni tekshirib qayta urinib ko‘ring.',
      );
    }
  }

  Future<Uint8List> download(String path) async {
    try {
      final response = await _client
          .get(uri(path), headers: headers)
          .timeout(const Duration(seconds: 45));
      if (response.statusCode >= 400) decode(response);
      return response.bodyBytes;
    } on ApiError {
      rethrow;
    } catch (_) {
      throw const ApiError('Fayl yuklab olinmadi. Ulanishni tekshiring.');
    }
  }

  void close() => _client.close();
}

class AppStore extends ChangeNotifier {
  AppStore() : api = ApiClient(_defaultServer());
  final ApiClient api;
  final FlutterSecureStorage storage = const FlutterSecureStorage();
  Json data = {};
  bool booting = true;
  bool refreshing = false;
  bool offline = false;
  String? error;

  static String _defaultServer() {
    const configured = String.fromEnvironment('API_BASE_URL');
    if (configured.isNotEmpty) return configured;
    if (kIsWeb) return Uri.base.origin;
    return 'http://10.0.2.2:8000';
  }

  Json get me => Map<String, dynamic>.from(data['me'] as Map? ?? {});
  Json get business =>
      Map<String, dynamic>.from(data['business'] as Map? ?? {});
  bool get signedIn => api.token != null;
  bool get hasWorkspace => data.isNotEmpty;
  bool get canEdit => !offline && ['owner', 'manager'].contains(me['role']);
  bool get isOwner => me['role'] == 'owner';
  String get currentDay => text(data['today']).isEmpty
      ? DateTime.now().toIso8601String().substring(0, 10)
      : text(data['today']);
  List<Json> rows(String name) => (data[name] as List? ?? [])
      .map((value) => Map<String, dynamic>.from(value as Map))
      .toList();
  Json? find(String collection, String id) {
    for (final row in rows(collection)) {
      if (row['id'] == id) return row;
    }
    return null;
  }

  Future<void> initialize() async {
    try {
      api.baseUrl = await storage.read(key: 'server') ?? api.baseUrl;
      api.token = await storage.read(key: 'session');
      if (api.token != null) {
        final cache = await storage.read(key: 'workspace');
        if (cache != null) data = jsonDecode(cache) as Json;
        await refresh();
      }
    } catch (_) {
      error = 'Saqlangan sessiya ochilmadi. Qayta kiring.';
      api.token = null;
      data = {};
    } finally {
      booting = false;
      notifyListeners();
    }
  }

  Future<void> setServer(String value) async {
    final cleaned = value.trim().replaceFirst(RegExp(r'/+$'), '');
    final parsed = Uri.tryParse(cleaned);
    if (parsed == null ||
        !['http', 'https'].contains(parsed.scheme) ||
        parsed.host.isEmpty ||
        (parsed.path.isNotEmpty && parsed.path != '/')) {
      throw const ApiError(
        'Server manzilini kiriting. Masalan, http://192.168.1.10:8000',
      );
    }
    api.baseUrl = cleaned;
    await storage.write(key: 'server', value: cleaned);
  }

  Future<void> authenticate(String action, Json payload) async {
    final response = await api.request(
      '/api/auth/$action',
      method: 'POST',
      body: payload,
    ) as Map;
    data = {};
    offline = false;
    error = null;
    api.token = text(response['token']);
    await storage.delete(key: 'workspace');
    await storage.write(key: 'session', value: api.token);
    await refresh();
    notifyListeners();
  }

  Future<bool> refresh() async {
    if (refreshing || api.token == null) return false;
    refreshing = true;
    notifyListeners();
    try {
      data = Map<String, dynamic>.from(
        await api.request('/api/workspace') as Map,
      );
      offline = false;
      error = null;
      try {
        await storage.write(key: 'workspace', value: jsonEncode(data));
      } catch (_) {
        error = 'Ma’lumot serverdan olindi. Qurilmada oflayn nusxa saqlanmadi.';
      }
      return true;
    } on ApiError catch (failure) {
      error = failure.message;
      offline = true;
      if (failure.status == 401) {
        api.token = null;
        data = {};
        await storage.delete(key: 'session');
        await storage.delete(key: 'workspace');
      }
      return false;
    } finally {
      refreshing = false;
      notifyListeners();
    }
  }

  Future<Json> mutate(
    String path,
    Json payload, {
    String method = 'POST',
    String? operationId,
  }) async {
    final result = await api.request(
      path,
      method: method,
      body: payload,
      operationId: operationId ?? uuid.v4(),
    );
    await refresh();
    return Map<String, dynamic>.from(result as Map);
  }

  Future<void> logout() async {
    try {
      await api.request('/api/auth/logout', method: 'POST');
    } on ApiError {
      // The local session is cleared even when the server is temporarily unreachable.
    }
    api.token = null;
    data = {};
    offline = false;
    error = null;
    await storage.delete(key: 'session');
    await storage.delete(key: 'workspace');
    notifyListeners();
  }

  Future<bool> saveFile(String path, String filename) async {
    final bytes = await api.download(path);
    final saved = await FilePicker.saveFile(
      dialogTitle: 'Faylni saqlash',
      fileName: filename,
      bytes: bytes,
    );
    return saved != null;
  }

  @override
  void dispose() {
    api.close();
    super.dispose();
  }
}
