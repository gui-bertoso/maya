"""Teaching, researched answers and exact aliases to supported commands."""
import re
from core.dialogue import DialogueEngine


class LearningEngine:
    SUPPORTED = ('launch_app','move_window','window_state','move_app','scale_app','window_showcase','hide_input_window')

    @staticmethod
    def clean(text):
        return text.strip().strip('"\'“”').strip()

    def handle(self, text, process):
        kb=process.knowledge_base
        memory=process.memory
        state=memory.state if memory else {}
        clean=process.normalize_text(text)
        # Teach an answer without turning any of its contents into instructions.
        match=re.fullmatch(r'(?:aprenda|aprende|ensinar|ensine|corrija|corrige|correcao|correção|teach|correct)\s*:\s*(.+?)\s*(?:=>|=)\s*(.+)',text,re.I|re.S)
        if match:
            question,answer=map(self.clean,match.groups())
            if not question or not answer:return True,'escreva a pergunta e a resposta separadas por =>.',None
            kb.teach_answer(question,answer,source='user')
            state['last_learning_question']=question
            return True,f'aprendi a resposta para “{question}”. você pode corrigir ou apagar depois.',None
        match=re.fullmatch(r'quando eu disser\s+["“](.+?)["”]\s*,?\s*(?:responda|responde|diga)\s+(.+)',text,re.I|re.S)
        if match:
            trigger,answer=map(self.clean,match.groups());kb.teach_answer(trigger,answer,source='user');state['last_learning_question']=trigger
            return True,f'aprendi como responder a “{trigger}”.',None
        match=re.fullmatch(r'quando eu disser\s+["“](.+?)["”]\s*,?\s*(?:faca|faça|execute)\s+(.+)',text,re.I|re.S)
        if match:
            trigger,command=map(self.clean,match.groups())
            if re.search(r'[;\n]|\s(?:e depois|and then)\s',command,re.I):
                return True,'nesta etapa posso aprender um comando por frase. ensine cada ação separadamente.',None
            if any(process.detect_patterns(trigger).get(flag) for flag in DialogueEngine.ACTIONS):
                return True,'essa frase já corresponde a um comando existente. escolha outra para não criar conflito.',None
            patterns=process.detect_patterns(command)
            if not any(patterns.get(key) for key in self.SUPPORTED):
                return True,'esse passo ainda não corresponde a uma ação que sei executar. posso guardar uma explicação, mas preciso de uma função implementada para ganhar essa habilidade.',None
            if patterns.get('launch_app') and (not process.app_launcher or not process.app_launcher.resolve_alias(patterns.get('app_alias',''))):
                return True,'não reconheci o aplicativo desse comando. confirme o nome de um app instalado antes de ensinar a frase.',None
            if kb.normalize_question(trigger)==kb.normalize_question(command):
                return True,'essa frase já é o próprio comando; não precisa de um atalho aprendido.',None
            kb.teach_skill(trigger,command)
            state['last_learning_question']=trigger
            return True,f'aprendi: quando você disser “{trigger}”, vou interpretar “{command}”. ainda não executei a ação.',None
        match=re.fullmatch(r'(?:pesquise\s+e\s+aprenda|pesquisa\s+e\s+aprende|aprenda|aprende)\s+(?:sobre\s+)?(.+)',text,re.I)
        if match:
            query=match.group(1).strip()
            if not process.web_assistant:return True,'a pesquisa web não está disponível agora.',None
            link=re.search(r'\s+(?:usando|em|com a fonte)\s+(https://\S+)\s*$',query,re.I)
            url=None
            if link:query,url=query[:link.start()].strip(),link.group(1)
            if process.parent is not None:process.parent.send_event('response_text',f'pesquisando sobre {query}...')
            result=process.web_assistant.research(query,url=url)
            if not result or not result.get('answer') or not result.get('sources'):
                return True,'não encontrei uma resposta com fonte suficientemente relacionada. você pode me ensinar com “aprenda: pergunta => resposta” ou indicar uma página com “usando https://...”.',None
            kb.teach_answer(query,result['answer'],source='web',sources=result['sources'])
            state['last_learning_question']=query
            return True,result['answer']+'\nfonte: '+result['sources'][0]['title']+'. guardei como informação pesquisada, ainda não verificada por você.',None
        match=re.fullmatch(r'(?:corrija isso|corrige isso|na verdade a resposta e|na verdade a resposta é)\s*:\s*(.+)',text,re.I|re.S)
        if match:
            question=state.get('last_learning_question')
            if not question:return True,'qual aprendizado você quer corrigir? use “corrija: pergunta => resposta”.',None
            kb.teach_answer(question,match.group(1).strip(),source='user')
            return True,f'corrigi o aprendizado sobre “{question}”. mantive a versão anterior no histórico.',None
        match=re.fullmatch(r'(?:esqueca|esqueça|apague|esquece)\s+(?:o\s+)?aprendizado\s+(?:sobre\s+)?(.+)',text,re.I)
        if match:
            removed=kb.forget(self.clean(match.group(1)))
            return True,'apaguei esse aprendizado.' if removed else 'não achei esse aprendizado com esse nome.',None
        if clean in {'fonte disso','qual a fonte disso','de onde aprendeu isso','de onde voce tirou isso'}:
            record=kb.get_record(state.get('last_learning_question',''))
            if not record:return True,'ainda não tenho um aprendizado recente para mostrar a fonte.',None
            if record['source']=='user':return True,'você me ensinou essa resposta diretamente.',None
            sources=record.get('sources',[])
            return True,('fontes: '+'; '.join(s['title']+': '+s['url'] for s in sources)) if sources else 'esse é um aprendizado antigo sem fonte registrada.',None
        if clean in {'o que voce aprendeu','lista aprendizados','listar aprendizados','mostra seus aprendizados'}:
            questions=list(kb.data['answers'])[-8:]
            skills=list(kb.data['skills'])[-8:]
            return True,'respostas: '+('; '.join(questions) or 'nenhuma')+'. frases de comando: '+('; '.join(skills) or 'nenhuma')+'.',None
        patterns=process.detect_patterns(text)
        # Existing explicit commands cannot be shadowed by a learned answer.
        if any(patterns.get(flag) for flag in DialogueEngine.ACTIONS):return False,None,None
        skill=kb.get_skill(text)
        if skill:
            if not any(process.detect_patterns(skill['command']).get(key) for key in self.SUPPORTED):
                return True,'a ação desse aprendizado não é mais reconhecida. ensine o comando novamente.',None
            return True,None,skill['command']
        record=kb.get_record(text)
        if record:
            state['last_learning_question']=text
            return True,record['answer'],None
        return False,None,None
