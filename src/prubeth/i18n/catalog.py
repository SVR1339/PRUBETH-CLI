"""PRUBETH 25-Language Translation Catalog.

Canonical message strings across all 25 supported developer languages.
Default baseline is formal British English (en_GB).
"""

from __future__ import annotations

from typing import Dict, Any

# Primary translation catalog mapping [locale_code][key] -> translated text string
TRANSLATION_CATALOG: Dict[str, Dict[str, str]] = {
    # 1. English (UK) - Foundational Baseline
    "en_GB": {
        "cli.banner.tagline": "PRUBETH Autonomous AI Developer CLI Runtime",
        "cli.prompt.placeholder": "Ask PRUBETH or enter a command (/help, /pin, /branch)...",
        "cli.status.thinking": "Analysing repository and formulating strategy...",
        "cli.status.executing_tool": "Executing tool '{tool}' with parameters: {args}",
        "cli.status.stagnation_alert": "Stagnation intercepted on tool '{tool}'. Steering execution trajectory.",
        "cli.status.healing": "Test failure detected. Engaging closed-loop autonomous repair...",
        "cli.status.success": "Operation completed successfully.",
        "cli.status.error": "Execution encountered an error: {error}",
        "cli.status.permission_denied": "Permission denied for operation '{action}'. Clearance level required: {level}",
        "cli.cmd.pin_success": "Pinned context artifact '{label}' successfully (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Unpinned context artifact (ID: {pin_id}).",
        "cli.cmd.branch_created": "Forked new conversation branch '{branch}' from {node_id}.",
        "cli.cmd.branch_switched": "Switched active conversation branch to '{branch}'.",
    },

    # 2. English (US)
    "en_US": {
        "cli.banner.tagline": "PRUBETH Autonomous AI Developer CLI Runtime",
        "cli.prompt.placeholder": "Ask PRUBETH or enter a command (/help, /pin, /branch)...",
        "cli.status.thinking": "Analyzing repository and formulating strategy...",
        "cli.status.executing_tool": "Executing tool '{tool}' with parameters: {args}",
        "cli.status.stagnation_alert": "Stagnation intercepted on tool '{tool}'. Steering execution trajectory.",
        "cli.status.healing": "Test failure detected. Engaging closed-loop autonomous repair...",
        "cli.status.success": "Operation completed successfully.",
        "cli.status.error": "Execution encountered an error: {error}",
        "cli.status.permission_denied": "Permission denied for operation '{action}'. Clearance level required: {level}",
        "cli.cmd.pin_success": "Pinned context artifact '{label}' successfully (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Unpinned context artifact (ID: {pin_id}).",
        "cli.cmd.branch_created": "Forked new conversation branch '{branch}' from {node_id}.",
        "cli.cmd.branch_switched": "Switched active conversation branch to '{branch}'.",
    },

    # 3. Spanish (Español)
    "es_ES": {
        "cli.banner.tagline": "PRUBETH Entorno de Ejecución CLI Autónomo para Desarrolladores",
        "cli.prompt.placeholder": "Pregunta a PRUBETH o escribe un comando (/help, /pin, /branch)...",
        "cli.status.thinking": "Analizando repositorio y formulando estrategia...",
        "cli.status.executing_tool": "Ejecutando herramienta '{tool}' con parámetros: {args}",
        "cli.status.stagnation_alert": "Estancamiento interceptado en la herramienta '{tool}'. Reorientando trayectoria.",
        "cli.status.healing": "Fallo en tests detectado. Iniciando reparación autónoma de ciclo cerrado...",
        "cli.status.success": "Operación completada con éxito.",
        "cli.status.error": "La ejecución encontró un error: {error}",
        "cli.status.permission_denied": "Permiso denegado para la operación '{action}'. Nivel requerido: {level}",
        "cli.cmd.pin_success": "Artefacto de contexto fijado con éxito '{label}' (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Artefacto de contexto desfijado (ID: {pin_id}).",
        "cli.cmd.branch_created": "Nueva rama de conversación '{branch}' creada desde {node_id}.",
        "cli.cmd.branch_switched": "Cambiado a la rama de conversación '{branch}'.",
    },

    # 4. French (Français)
    "fr_FR": {
        "cli.banner.tagline": "PRUBETH Environnement d'Exécution CLI Autonome pour Développeurs",
        "cli.prompt.placeholder": "Posez une question à PRUBETH ou entrez une commande...",
        "cli.status.thinking": "Analyse du dépôt et formulation de la stratégie...",
        "cli.status.executing_tool": "Exécution de l'outil '{tool}' avec les paramètres: {args}",
        "cli.status.stagnation_alert": "Stagnation interceptée sur l'outil '{tool}'. Redirection de la trajectoire.",
        "cli.status.healing": "Échec des tests détecté. Lancement de la réparation autonome...",
        "cli.status.success": "Opération terminée avec succès.",
        "cli.status.error": "L'exécution a rencontré une erreur: {error}",
        "cli.status.permission_denied": "Permission refusée pour l'opération '{action}'. Niveau requis: {level}",
        "cli.cmd.pin_success": "Artefact de contexte épinglé avec succès '{label}' (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Artefact de contexte désépinglé (ID: {pin_id}).",
        "cli.cmd.branch_created": "Nouvelle branche de conversation '{branch}' créée depuis {node_id}.",
        "cli.cmd.branch_switched": "Branche active changée pour '{branch}'.",
    },

    # 5. German (Deutsch)
    "de_DE": {
        "cli.banner.tagline": "PRUBETH Autonome Entwickler-CLI-Laufzeitumgebung",
        "cli.prompt.placeholder": "Fragen Sie PRUBETH oder geben Sie einen Befehl ein...",
        "cli.status.thinking": "Analysiere Repository und erstelle Strategie...",
        "cli.status.executing_tool": "Führe Werkzeug '{tool}' mit Parametern aus: {args}",
        "cli.status.stagnation_alert": "Stagnation bei Werkzeug '{tool}' abgefangen. Ausführung wird umgeleitet.",
        "cli.status.healing": "Testfehler erkannt. Starte autonome Selbstreparatur...",
        "cli.status.success": "Vorgang erfolgreich abgeschlossen.",
        "cli.status.error": "Ausführungsfehler aufgetreten: {error}",
        "cli.status.permission_denied": "Berechtigung verweigert für '{action}'. Erforderliche Stufe: {level}",
        "cli.cmd.pin_success": "Kontext-Artefakt '{label}' erfolgreich angeheftet (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Kontext-Artefakt gelöst (ID: {pin_id}).",
        "cli.cmd.branch_created": "Neuen Gesprächszweig '{branch}' von {node_id} abgezweigt.",
        "cli.cmd.branch_switched": "Aktiven Gesprächszweig zu '{branch}' gewechselt.",
    },

    # 6. Japanese (日本語)
    "ja_JP": {
        "cli.banner.tagline": "PRUBETH 自律型AI開発者CLIランタイム",
        "cli.prompt.placeholder": "PRUBETHに質問するかコマンドを入力してください...",
        "cli.status.thinking": "リポジトリを分析し戦略を策定中...",
        "cli.status.executing_tool": "ツール '{tool}' をパラメータで実行中: {args}",
        "cli.status.stagnation_alert": "ツール '{tool}' の停滞を検知しました。実行方針を調整します。",
        "cli.status.healing": "テスト失敗を検出しました。自律的自己修復を開始します...",
        "cli.status.success": "処理が正常に完了しました。",
        "cli.status.error": "実行エラーが発生しました: {error}",
        "cli.status.permission_denied": "操作 '{action}' の権限が拒否されました。必要な権限レベル: {level}",
        "cli.cmd.pin_success": "コンテキスト成果物 '{label}' を固定しました (ID: {pin_id})。",
        "cli.cmd.unpin_success": "コンテキスト成果物の固定を解除しました (ID: {pin_id})。",
        "cli.cmd.branch_created": "ノード {node_id} から新しい対話ブランチ '{branch}' を作成しました。",
        "cli.cmd.branch_switched": "アクティブな対話ブランチを '{branch}' に切り替えました。",
    },

    # 7. Chinese Simplified (简体中文)
    "zh_CN": {
        "cli.banner.tagline": "PRUBETH 自主AI开发者命令行运行时",
        "cli.prompt.placeholder": "向 PRUBETH 提问或输入命令 (/help, /pin, /branch)...",
        "cli.status.thinking": "正在分析仓库并制定策略...",
        "cli.status.executing_tool": "正在执行工具 '{tool}'，参数: {args}",
        "cli.status.stagnation_alert": "检测到工具 '{tool}' 停滞。正在调整执行轨迹。",
        "cli.status.healing": "检测到测试失败。正在启动闭环自主修复...",
        "cli.status.success": "操作成功完成。",
        "cli.status.error": "执行遇到错误: {error}",
        "cli.status.permission_denied": "操作 '{action}' 权限不足。所需权限等级: {level}",
        "cli.cmd.pin_success": "已成功固定上下文构件 '{label}' (ID: {pin_id})。",
        "cli.cmd.unpin_success": "已取消固定上下文构件 (ID: {pin_id})。",
        "cli.cmd.branch_created": "已从 {node_id} 分支创建新对话分支 '{branch}'。",
        "cli.cmd.branch_switched": "已切换当前活动对话分支为 '{branch}'。",
    },

    # 8. Chinese Traditional (繁體中文)
    "zh_TW": {
        "cli.banner.tagline": "PRUBETH 自主AI開發者命令列執行環境",
        "cli.prompt.placeholder": "向 PRUBETH 提問或輸入命令 (/help, /pin, /branch)...",
        "cli.status.thinking": "正在分析儲存庫並制定策略...",
        "cli.status.executing_tool": "正在執行工具 '{tool}'，參數: {args}",
        "cli.status.stagnation_alert": "偵測到工具 '{tool}' 停滯。正在調整執行軌跡。",
        "cli.status.healing": "偵測到測試失敗。正在啟動閉環自主修復...",
        "cli.status.success": "操作成功完成。",
        "cli.status.error": "執行遇到錯誤: {error}",
        "cli.status.permission_denied": "操作 '{action}' 權限不足。所需權限等級: {level}",
        "cli.cmd.pin_success": "已成功固定上下文構件 '{label}' (ID: {pin_id})。",
        "cli.cmd.unpin_success": "已取消固定上下文構件 (ID: {pin_id})。",
        "cli.cmd.branch_created": "已從 {node_id} 建立新對話分支 '{branch}'。",
        "cli.cmd.branch_switched": "已切換目前使用對話分支為 '{branch}'。",
    },

    # 9. Korean (한국어)
    "ko_KR": {
        "cli.banner.tagline": "PRUBETH 자율형 AI 개발자 CLI 런타임",
        "cli.prompt.placeholder": "PRUBETH에 질문하거나 명령어를 입력하세요 (/help, /pin, /branch)...",
        "cli.status.thinking": "저장소를 분석하고 전략을 수립하는 중...",
        "cli.status.executing_tool": "도구 '{tool}' 실행 중 (매개변수: {args})",
        "cli.status.stagnation_alert": "도구 '{tool}'에서 정체가 감지되었습니다. 실행 궤도를 조정합니다.",
        "cli.status.healing": "테스트 실패가 감지되었습니다. 자율 자가 수정을 시작합니다...",
        "cli.status.success": "작업이 성공적으로 완료되었습니다.",
        "cli.status.error": "실행 중 오류가 발생했습니다: {error}",
        "cli.status.permission_denied": "'{action}' 작업 권한이 거부되었습니다. 요구 등급: {level}",
        "cli.cmd.pin_success": "컨텍스트 항목 '{label}' 고정 완료 (ID: {pin_id}).",
        "cli.cmd.unpin_success": "컨텍스트 항목 고정 해제 (ID: {pin_id}).",
        "cli.cmd.branch_created": "{node_id}에서 새 대화 브랜치 '{branch}' 생성 완료.",
        "cli.cmd.branch_switched": "활성 대화 브랜치를 '{branch}'(으)로 전환했습니다.",
    },

    # 10. Portuguese Brazil (Português)
    "pt_BR": {
        "cli.banner.tagline": "PRUBETH Ambiente de Execução CLI Autônomo para Desenvolvedores",
        "cli.prompt.placeholder": "Pergunte ao PRUBETH ou digite um comando (/help, /pin, /branch)...",
        "cli.status.thinking": "Analisando repositório e formulando estratégia...",
        "cli.status.executing_tool": "Executando ferramenta '{tool}' com parâmetros: {args}",
        "cli.status.stagnation_alert": "Estagnação interceptada na ferramenta '{tool}'. Redirecionando trajetória.",
        "cli.status.healing": "Falha de teste detectada. Iniciando reparo autônomo em malha fechada...",
        "cli.status.success": "Operação concluída com sucesso.",
        "cli.status.error": "A execução encontrou um erro: {error}",
        "cli.status.permission_denied": "Permissão negada para a operação '{action}'. Nível necessário: {level}",
        "cli.cmd.pin_success": "Artefato de contexto fixado com sucesso '{label}' (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Artefato de contexto desfixado (ID: {pin_id}).",
        "cli.cmd.branch_created": "Nova ramificação de conversa '{branch}' criada a partir de {node_id}.",
        "cli.cmd.branch_switched": "Ramificação de conversa alterada para '{branch}'.",
    },

    # 11. Russian (Русский)
    "ru_RU": {
        "cli.banner.tagline": "PRUBETH Автономная среда выполнения CLI для разработчиков",
        "cli.prompt.placeholder": "Задайте вопрос PRUBETH или введите команду (/help, /pin, /branch)...",
        "cli.status.thinking": "Анализ репозитория и формирование стратегии...",
        "cli.status.executing_tool": "Выполнение инструмента '{tool}' с параметрами: {args}",
        "cli.status.stagnation_alert": "Обнаружено зацикливание на инструменте '{tool}'. Коррекция траектории.",
        "cli.status.healing": "Обнаружен сбой тестов. Запуск автономного исправления...",
        "cli.status.success": "Операция успешно завершена.",
        "cli.status.error": "Ошибка при выполнении: {error}",
        "cli.status.permission_denied": "Отказано в доступе для операции '{action}'. Требуемый уровень: {level}",
        "cli.cmd.pin_success": "Контекстный артефакт '{label}' успешно закреплен (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Контекстный артефакт откреплен (ID: {pin_id}).",
        "cli.cmd.branch_created": "Создана новая ветка диалога '{branch}' от узла {node_id}.",
        "cli.cmd.branch_switched": "Активная ветка переключена на '{branch}'.",
    },

    # 12. Italian (Italiano)
    "it_IT": {
        "cli.banner.tagline": "PRUBETH Runtime CLI Autonomo per Sviluppatori",
        "cli.prompt.placeholder": "Chiedi a PRUBETH o inserisci un comando (/help, /pin, /branch)...",
        "cli.status.thinking": "Analisi del repository e formulazione della strategia...",
        "cli.status.executing_tool": "Esecuzione dello strumento '{tool}' con parametri: {args}",
        "cli.status.stagnation_alert": "Rilevato blocco sullo strumento '{tool}'. Correzione della traiettoria.",
        "cli.status.healing": "Rilevato errore nei test. Avvio riparazione autonoma...",
        "cli.status.success": "Operazione completata con successo.",
        "cli.status.error": "Errore durante l'esecuzione: {error}",
        "cli.status.permission_denied": "Permesso negato per l'operazione '{action}'. Livello richiesto: {level}",
        "cli.cmd.pin_success": "Elemento di contesto '{label}' fissato con successo (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Elemento di contesto rimosso dai fissati (ID: {pin_id}).",
        "cli.cmd.branch_created": "Nuovo ramo di conversazione '{branch}' creato da {node_id}.",
        "cli.cmd.branch_switched": "Ramo di conversazione attivo impostato su '{branch}'.",
    },

    # 13. Dutch (Nederlands)
    "nl_NL": {
        "cli.banner.tagline": "PRUBETH Autonome AI-ontwikkelaars CLI-runtime",
        "cli.prompt.placeholder": "Vraag PRUBETH of voer een commando in (/help, /pin, /branch)...",
        "cli.status.thinking": "Repository analyseren en strategie formuleren...",
        "cli.status.executing_tool": "Tool '{tool}' uitvoeren met parameters: {args}",
        "cli.status.stagnation_alert": "Stagnatie onderschept bij tool '{tool}'. Koers corrigeren.",
        "cli.status.healing": "Testfout gedetecteerd. Autonome herstelcyclus gestart...",
        "cli.status.success": "Bewerking succesvol voltooid.",
        "cli.status.error": "Fout opgetreden tijdens uitvoering: {error}",
        "cli.status.permission_denied": "Toegang geweigerd voor '{action}'. Vereist niveau: {level}",
        "cli.cmd.pin_success": "Context-item '{label}' succesvol vastgezet (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Context-item losgemaakt (ID: {pin_id}).",
        "cli.cmd.branch_created": "Nieuwe gesprekstak '{branch}' aangemaakt vanaf {node_id}.",
        "cli.cmd.branch_switched": "Actieve gesprekstak gewijzigd naar '{branch}'.",
    },

    # 14. Polish (Polski)
    "pl_PL": {
        "cli.banner.tagline": "PRUBETH Autonomiczne Środowisko CLI dla Programistów",
        "cli.prompt.placeholder": "Zapytaj PRUBETH lub wpisz polecenie (/help, /pin, /branch)...",
        "cli.status.thinking": "Analizowanie repozytorium i opracowywanie strategii...",
        "cli.status.executing_tool": "Wykonywanie narzędzia '{tool}' z parametrami: {args}",
        "cli.status.stagnation_alert": "Wykryto zapętlenie w narzędziu '{tool}'. Korygowanie ścieżki.",
        "cli.status.healing": "Wykryto błąd testów. Uruchamianie autonomicznej naprawy...",
        "cli.status.success": "Operacja zakończona pomyślnie.",
        "cli.status.error": "Wystąpił błąd podczas wykonywania: {error}",
        "cli.status.permission_denied": "Brak uprawnień do operacji '{action}'. Wymagany poziom: {level}",
        "cli.cmd.pin_success": "Przypięto element kontekstu '{label}' (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Odpięto element kontekstu (ID: {pin_id}).",
        "cli.cmd.branch_created": "Utworzono nową gałąź rozmowy '{branch}' z węzła {node_id}.",
        "cli.cmd.branch_switched": "Przełączono aktywną gałąź rozmowy na '{branch}'.",
    },

    # 15. Turkish (Türkçe)
    "tr_TR": {
        "cli.banner.tagline": "PRUBETH Otonom Yapay Zeka Geliştirici CLI Çalışma Zamanı",
        "cli.prompt.placeholder": "PRUBETH'e sorun veya bir komut girin (/help, /pin, /branch)...",
        "cli.status.thinking": "Depo analiz ediliyor ve strateji belirleniyor...",
        "cli.status.executing_tool": "'{tool}' aracı şu parametrelerle çalıştırılıyor: {args}",
        "cli.status.stagnation_alert": "'{tool}' aracında kilitlenme tespit edildi. Yörünge ayarlanıyor.",
        "cli.status.healing": "Test hatası algılandı. Otonom onarım başlatılıyor...",
        "cli.status.success": "İşlem başarıyla tamamlandı.",
        "cli.status.error": "Çalıştırma sırasında bir hata oluştu: {error}",
        "cli.status.permission_denied": "'{action}' işlemi için izin reddedildi. Gereken seviye: {level}",
        "cli.cmd.pin_success": "'{label}' bağlam öğesi başarıyla sabitlendi (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Bağlam öğesinin sabitlemesi kaldırıldı (ID: {pin_id}).",
        "cli.cmd.branch_created": "{node_id} düğümünden yeni konuşma dalı '{branch}' oluşturuldu.",
        "cli.cmd.branch_switched": "Etkin konuşma dalı '{branch}' olarak değiştirildi.",
    },

    # 16. Arabic (العربية - RTL)
    "ar_SA": {
        "cli.banner.tagline": "PRUBETH بيئة تشغيل سطر الأوامر المستقلة للمطورين",
        "cli.prompt.placeholder": "اسأل PRUBETH أو أدخل أمراً (/help, /pin, /branch)...",
        "cli.status.thinking": "جارٍ تحليل المستودع وصياغة الاستراتيجية...",
        "cli.status.executing_tool": "جارٍ تنفيذ الأداة '{tool}' بالمعلمات: {args}",
        "cli.status.stagnation_alert": "تم رصد تكرار غير مجدٍ في الأداة '{tool}'. جارٍ تعديل المسار.",
        "cli.status.healing": "تم رصد فشل في الاختبارات. جارٍ بدء الإصلاح الذاتي...",
        "cli.status.success": "تمت العملية بنجاح.",
        "cli.status.error": "حدث خطأ أثناء التنفيذ: {error}",
        "cli.status.permission_denied": "تم رفض الإذن للعملية '{action}'. المستوى المطلوب: {level}",
        "cli.cmd.pin_success": "تم تثبيت عنصر السياق '{label}' بنجاح (المعرف: {pin_id}).",
        "cli.cmd.unpin_success": "تم إلغاء تثبيت عنصر السياق (المعرف: {pin_id}).",
        "cli.cmd.branch_created": "تم إنشاء فرع محادثة جديد '{branch}' من {node_id}.",
        "cli.cmd.branch_switched": "تم تحويل فرع المحادثة النشط إلى '{branch}'.",
    },

    # 17. Hindi (हिन्दी)
    "hi_IN": {
        "cli.banner.tagline": "PRUBETH स्वायत्त एआई डेवलपर सीएलआई रनटाइम",
        "cli.prompt.placeholder": "PRUBETH से पूछें या कमांड दर्ज करें (/help, /pin, /branch)...",
        "cli.status.thinking": "रिपॉजिटरी का विश्लेषण और रणनीति तैयार की जा रही है...",
        "cli.status.executing_tool": "टूल '{tool}' को इन मापदंडों के साथ निष्पादित किया जा रहा है: {args}",
        "cli.status.stagnation_alert": "टूल '{tool}' में ठहराव का पता चला। निष्पादन दिशा बदली जा रही है।",
        "cli.status.healing": "परीक्षण विफलता मिली। स्वायत्त स्व-मरम्मत शुरू की जा रही है...",
        "cli.status.success": "ऑपरेशन सफलतापूर्वक पूरा हुआ।",
        "cli.status.error": "निष्पादन में त्रुटि आई: {error}",
        "cli.status.permission_denied": "'{action}' के लिए अनुमति अस्वीकृत। आवश्यक स्तर: {level}",
        "cli.cmd.pin_success": "संदर्भ कलाकृति '{label}' सफलतापूर्वक पिन की गई (ID: {pin_id})।",
        "cli.cmd.unpin_success": "संदर्भ कलाकृति अनपिन की गई (ID: {pin_id})।",
        "cli.cmd.branch_created": "{node_id} से नई बातचीत शाखा '{branch}' बनाई गई।",
        "cli.cmd.branch_switched": "सक्रिय बातचीत शाखा को '{branch}' पर स्विच किया गया।",
    },

    # 18. Bengali (বাংলা)
    "bn_BD": {
        "cli.banner.tagline": "PRUBETH স্বায়ত্তশাসিত এআই ডেভেলপার সিএলআই রানটাইম",
        "cli.prompt.placeholder": "PRUBETH-কে জিজ্ঞাসা করুন বা একটি কমান্ড লিখুন...",
        "cli.status.thinking": "রিপোজিটরি বিশ্লেষণ এবং কৌশল তৈরি করা হচ্ছে...",
        "cli.status.executing_tool": "টুল '{tool}' চালানো হচ্ছে প্যারামিটার সহ: {args}",
        "cli.status.stagnation_alert": "টুল '{tool}'-এ স্থবিরতা সনাক্ত করা হয়েছে। পথ পরিবর্তন করা হচ্ছে।",
        "cli.status.healing": "টেস্ট ব্যর্থতা সনাক্ত হয়েছে। স্বয়ংক্রিয় মেরামত শুরু হচ্ছে...",
        "cli.status.success": "অপারেশন সফলভাবে সম্পন্ন হয়েছে।",
        "cli.status.error": "সম্পাদনে ত্রুটি ঘটেছে: {error}",
        "cli.status.permission_denied": "'{action}'-এর অনুমতি প্রত্যাখ্যাত। প্রয়োজনীয় স্তর: {level}",
        "cli.cmd.pin_success": "প্রসঙ্গ আর্টিফ্যাক্ট '{label}' সফলভাবে পিন করা হয়েছে (ID: {pin_id})।",
        "cli.cmd.unpin_success": "প্রসঙ্গ আর্টিফ্যাক্ট আনপিন করা হয়েছে (ID: {pin_id})।",
        "cli.cmd.branch_created": "{node_id} থেকে নতুন কথোপকথন শাখা '{branch}' তৈরি হয়েছে।",
        "cli.cmd.branch_switched": "সক্রিয় শাখা '{branch}'-এ পরিবর্তিত হয়েছে।",
    },

    # 19. Swedish (Svenska)
    "sv_SE": {
        "cli.banner.tagline": "PRUBETH Autonom AI-utvecklare CLI-körtid",
        "cli.prompt.placeholder": "Fråga PRUBETH eller ange ett kommando (/help, /pin, /branch)...",
        "cli.status.thinking": "Analyserar kodarkiv och utformar strategi...",
        "cli.status.executing_tool": "Kör verktyg '{tool}' med parametrar: {args}",
        "cli.status.stagnation_alert": "Stagnation upptäckt i verktyg '{tool}'. Justerar körningsriktning.",
        "cli.status.healing": "Testfel upptäckt. Startar autonom självläkning...",
        "cli.status.success": "Åtgärden slutfördes framgångsrikt.",
        "cli.status.error": "Körningen stötte på ett fel: {error}",
        "cli.status.permission_denied": "Åtkomst nekad för åtgärden '{action}'. Erfordrad nivå: {level}",
        "cli.cmd.pin_success": "Kontextobjekt '{label}' har fästs (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Kontextobjekt har lösgjorts (ID: {pin_id}).",
        "cli.cmd.branch_created": "Skapade ny konversationsgren '{branch}' från {node_id}.",
        "cli.cmd.branch_switched": "Växlade aktiv konversationsgren till '{branch}'.",
    },

    # 20. Ukrainian (Українська)
    "uk_UA": {
        "cli.banner.tagline": "PRUBETH Автономне середовище CLI для розробників",
        "cli.prompt.placeholder": "Запитайте PRUBETH або введіть команду (/help, /pin, /branch)...",
        "cli.status.thinking": "Аналіз репозиторію та формування стратегії...",
        "cli.status.executing_tool": "Виконання інструменту '{tool}' з параметрами: {args}",
        "cli.status.stagnation_alert": "Виявлено зациклення на інструменті '{tool}'. Коригування траєкторії.",
        "cli.status.healing": "Виявлено помилку в тестах. Запуск автономного виправлення...",
        "cli.status.success": "Операцію успішно завершено.",
        "cli.status.error": "Виникла помилка під час виконання: {error}",
        "cli.status.permission_denied": "Відмовлено в доступі для операції '{action}'. Необхідний рівень: {level}",
        "cli.cmd.pin_success": "Контекстний артефакт '{label}' успішно закріплено (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Контекстний артефакт відкріплено (ID: {pin_id}).",
        "cli.cmd.branch_created": "Створено нову гілку діалогу '{branch}' від вузла {node_id}.",
        "cli.cmd.branch_switched": "Активну гілку перемкнуто на '{branch}'.",
    },

    # 21. Vietnamese (Tiếng Việt)
    "vi_VN": {
        "cli.banner.tagline": "PRUBETH Môi trường Thực thi CLI Tự trị dành cho Lập trình viên",
        "cli.prompt.placeholder": "Hỏi PRUBETH hoặc nhập lệnh (/help, /pin, /branch)...",
        "cli.status.thinking": "Đang phân tích kho lưu trữ và xây dựng chiến lược...",
        "cli.status.executing_tool": "Đang thực thi công cụ '{tool}' với tham số: {args}",
        "cli.status.stagnation_alert": "Phát hiện đình trệ ở công cụ '{tool}'. Đang điều chỉnh quỹ đạo.",
        "cli.status.healing": "Phát hiện kiểm thử thất bại. Bắt đầu tự động sửa chữa khép kín...",
        "cli.status.success": "Thao tác hoàn tất thành công.",
        "cli.status.error": "Quá trình thực thi gặp lỗi: {error}",
        "cli.status.permission_denied": "Quyền bị từ chối cho thao tác '{action}'. Cấp độ yêu cầu: {level}",
        "cli.cmd.pin_success": "Đã ghim thành công mục ngữ cảnh '{label}' (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Đã bỏ ghim mục ngữ cảnh (ID: {pin_id}).",
        "cli.cmd.branch_created": "Đã tạo nhánh hội thoại mới '{branch}' từ nút {node_id}.",
        "cli.cmd.branch_switched": "Đã chuyển nhánh hội thoại hiện tại sang '{branch}'.",
    },

    # 22. Indonesian (Bahasa Indonesia)
    "id_ID": {
        "cli.banner.tagline": "PRUBETH Lingkungan Eksekusi CLI Otonom untuk Pengembang",
        "cli.prompt.placeholder": "Tanya PRUBETH atau masukkan perintah (/help, /pin, /branch)...",
        "cli.status.thinking": "Menganalisis repositori dan merumuskan strategi...",
        "cli.status.executing_tool": "Menjalankan alat '{tool}' dengan parameter: {args}",
        "cli.status.stagnation_alert": "Stagnasi terdeteksi pada alat '{tool}'. Mengarahkan jalur eksekusi.",
        "cli.status.healing": "Kegagalan pengujian terdeteksi. Memulai perbaikan mandiri...",
        "cli.status.success": "Operasi berhasil diselesaikan.",
        "cli.status.error": "Eksekusi mengalami kesalahan: {error}",
        "cli.status.permission_denied": "Izin ditolak untuk operasi '{action}'. Tingkat yang diperlukan: {level}",
        "cli.cmd.pin_success": "Artefak konteks '{label}' berhasil disematkan (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Artefak konteks dilepas (ID: {pin_id}).",
        "cli.cmd.branch_created": "Cabang percakapan baru '{branch}' dibuat dari {node_id}.",
        "cli.cmd.branch_switched": "Cabang percakapan aktif dialihkan ke '{branch}'.",
    },

    # 23. Greek (Ελληνικά)
    "el_GR": {
        "cli.banner.tagline": "PRUBETH Αυτόνομο Περιβάλλον Εκτέλεσης CLI για Προγραμματιστές",
        "cli.prompt.placeholder": "Ρωτήστε το PRUBETH ή πληκτρολογήστε μια εντολή...",
        "cli.status.thinking": "Ανάλυση αποθετηρίου και διαμόρφωση στρατηγικής...",
        "cli.status.executing_tool": "Εκτέλεση εργαλείου '{tool}' με παραμέτρους: {args}",
        "cli.status.stagnation_alert": "Εντοπίστηκε στασιμότητα στο εργαλείο '{tool}'. Προσαρμογή κατεύθυνσης.",
        "cli.status.healing": "Εντοπίστηκε αποτυχία δοκιμών. Έναρξη αυτόνομης διόρθωσης...",
        "cli.status.success": "Η λειτουργία ολοκληρώθηκε με επιτυχία.",
        "cli.status.error": "Παρουσιάστηκε σφάλμα κατά την εκτέλεση: {error}",
        "cli.status.permission_denied": "Δεν επιτρέπεται η λειτουργία '{action}'. Απαιτούμενο επίπεδο: {level}",
        "cli.cmd.pin_success": "Το στοιχείο πλαισίου '{label}' καρφιτσώθηκε επιτυχώς (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Το στοιχείο πλαισίου ξεκαρφιτσώθηκε (ID: {pin_id}).",
        "cli.cmd.branch_created": "Δημιουργήθηκε νέος κλάδος συνομιλίας '{branch}' από τον κόμβο {node_id}.",
        "cli.cmd.branch_switched": "Ενεργός κλάδος συνομιλίας άλλαξε σε '{branch}'.",
    },

    # 24. Czech (Čeština)
    "cs_CZ": {
        "cli.banner.tagline": "PRUBETH Autonomní Vývojářské CLI Běhové Prostředí",
        "cli.prompt.placeholder": "Zeptejte se PRUBETH nebo zadejte příkaz (/help, /pin, /branch)...",
        "cli.status.thinking": "Analyzuji repozitář a formuluji strategii...",
        "cli.status.executing_tool": "Spouštím nástroj '{tool}' s parametry: {args}",
        "cli.status.stagnation_alert": "Zjištěna stagnace u nástroje '{tool}'. Upravuji směr běhu.",
        "cli.status.healing": "Zjištěno selhání testů. Spouštím autonomní samoopravu...",
        "cli.status.success": "Operace byla úspěšně dokončena.",
        "cli.status.error": "Při provádění došlo k chybě: {error}",
        "cli.status.permission_denied": "Oprávnění zamítnuto pro operaci '{action}'. Požadovaná úroveň: {level}",
        "cli.cmd.pin_success": "Kontextová položka '{label}' úspěšně připnuta (ID: {pin_id}).",
        "cli.cmd.unpin_success": "Kontextová položka odepnuta (ID: {pin_id}).",
        "cli.cmd.branch_created": "Vytvořena nová větev konverzace '{branch}' z uzlu {node_id}.",
        "cli.cmd.branch_switched": "Aktivní větev konverzace přepnuta na '{branch}'.",
    },

    # 25. Hebrew (עברית - RTL)
    "he_IL": {
        "cli.banner.tagline": "PRUBETH סביבת שורת פקודה אוטונומית למפתחים מבוססת AI",
        "cli.prompt.placeholder": "שאל את PRUBETH או הזן פקודה (/help, /pin, /branch)...",
        "cli.status.thinking": "מנתח את המאגר ומגבש אסטרטגיה...",
        "cli.status.executing_tool": "מפעיל את הכלי '{tool}' עם הפרמטרים: {args}",
        "cli.status.stagnation_alert": "זוהתה תקיעות בהפעלת הכלי '{tool}'. מתאים כיוון ביצוע.",
        "cli.status.healing": "זוהה כשל בבדיקות. מפעיל תיקון אוטונומי במעגל סגור...",
        "cli.status.success": "הפעולה הושלמה בהצלחה.",
        "cli.status.error": "אירעה שגיאה במהלך הביצוע: {error}",
        "cli.status.permission_denied": "ההרשאה נדחתה עבור הפעולה '{action}'. נדרשת רמת הרשאה: {level}",
        "cli.cmd.pin_success": "פריט ההקשר '{label}' הוצמד בהצלחה (מזהה: {pin_id}).",
        "cli.cmd.unpin_success": "הסרת הצמדת פריט ההקשר (מזהה: {pin_id}).",
        "cli.cmd.branch_created": "נוצר ענף שיחה חדש '{branch}' מהצומת {node_id}.",
        "cli.cmd.branch_switched": "ענף השיחה הפעיל הוחלף ל-'{branch}'.",
    },
}
