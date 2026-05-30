grammar Calc;

expr : term (PLUS term)* ;
term : NUMBER ;

PLUS : '+' ;
NUMBER : [0-9]+ ;
WS : [ \t\r\n]+ -> skip ;
