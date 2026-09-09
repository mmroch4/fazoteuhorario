/* Horários que acompanham o site, mostrados em "Horários guardados" como
   "Exemplos incluídos" — só de leitura, iguais para toda a gente.

   Os horários de cada pessoa NÃO vivem aqui: ficam no navegador dela
   (localStorage, chave "fcup-presets-v1"), guardados pelo botão "Guardar o
   horário atual". Isto é só para distribuir um horário com o próprio site.

   Formato de cada entrada:
     name   obrigatório — o título do botão
     picks  obrigatório — nomes das turmas, tal como aparecem nos dados
     note   opcional    — linha de descrição por baixo do nome
     skips  opcional    — aulas a marcar como falta, "TURMA|dia|HH:MM"
                          (dia: 0 = segunda … 5 = sábado)
     sem    opcional    — "1S" ou "2S"; carregar o horário troca o semestre

   Gerado por:  python3 scripts/solve_schedule.py <códigos> --save-preset="Nome"     */
window.TIMETABLE_PRESETS = [];
